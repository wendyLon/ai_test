"""Generic container entrypoint for running agent workers with health, heartbeat and metrics."""
import os
import asyncio
import signal
import socket
import time
import json
import importlib
from aiohttp import web

from platform.redis_client import get_redis_client
from platform.observability.logging import setup_logging, get_logger
from platform.observability.otel import init_tracer
from platform.observability.metrics import start_prometheus


HEARTBEAT_INTERVAL = int(os.environ.get('HEARTBEAT_INTERVAL', '10'))
METRICS_PORT = int(os.environ.get('METRICS_PORT', '8000'))
HEALTH_PORT = int(os.environ.get('HEALTH_PORT', '8000'))
NAMESPACE = os.environ.get('NAMESPACE', 'sen')
AGENT_NAME = os.environ.get('AGENT_NAME', 'worker')
WORKER_CLASS = os.environ.get('WORKER_CLASS')
REDIS_URL = os.environ.get('REDIS_URL')
MODE = os.environ.get('MODE', 'local')


async def heartbeat_task(r, ns, agent, hostname):
    key = f"{ns}:heartbeat:{agent}:{hostname}"
    while True:
        try:
            payload = json.dumps({'ts': time.time(), 'agent': agent, 'mode': MODE})
            r.set(key, payload)
            r.expire(key, HEARTBEAT_INTERVAL * 3)
        except Exception:
            pass
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def start_health_server(app):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', HEALTH_PORT)
    await site.start()


def make_health_app(agent, start_ts):
    app = web.Application()

    async def health(request):
        uptime = time.time() - start_ts
        return web.json_response({'status': 'ok', 'agent': agent, 'uptime': uptime})

    app.router.add_get('/health', health)
    return app


async def run_worker():
    setup_logging()
    init_tracer()
    # start prometheus server if desired
    try:
        start_prometheus(METRICS_PORT)
    except Exception:
        pass

    logger = get_logger(f'container.{AGENT_NAME}')
    logger.info('starting container entry', extra={'agent': AGENT_NAME, 'mode': MODE})

    r = get_redis_client(REDIS_URL)
    hostname = socket.gethostname()
    start_ts = time.time()

    # start heartbeat
    hb = asyncio.create_task(heartbeat_task(r, NAMESPACE, AGENT_NAME, hostname))

    # start health server
    app = make_health_app(AGENT_NAME, start_ts)
    await start_health_server(app)

    # instantiate worker
    if not WORKER_CLASS:
        logger.error('WORKER_CLASS not provided')
        return

    try:
        module_name, cls_name = WORKER_CLASS.split(':')
        mod = importlib.import_module(module_name)
        cls = getattr(mod, cls_name)
    except Exception as e:
        logger.error('failed_import_worker', extra={'error': str(e), 'worker_class': WORKER_CLASS})
        return

    # try common constructor patterns
    try:
        worker = cls(agent_name=AGENT_NAME, namespace=NAMESPACE, redis_url=REDIS_URL)
    except TypeError:
        try:
            worker = cls(AGENT_NAME)
        except Exception:
            worker = cls()

    # run worker in background
    worker_task = asyncio.create_task(worker.run())

    # graceful shutdown
    stop_event = asyncio.Event()

    def _signal(_sig):
        logger.info('shutdown_signal', extra={'signal': str(_sig)})
        stop_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: _signal('SIGTERM'))
    loop.add_signal_handler(signal.SIGINT, lambda: _signal('SIGINT'))

    await stop_event.wait()
    logger.info('stopping worker')
    await worker.stop()
    worker_task.cancel()
    hb.cancel()


def main():
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
