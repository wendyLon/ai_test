"""Example worker process for DiscoveryAgent using Redis-backed WorkerBase.

Run as: python scripts/example_worker.py discovery
"""
import asyncio
import sys
from platform.worker_base import WorkerBase
from platform.agents.discovery.discovery_agent import DiscoveryAgent
from platform.queue_manager import QueueManager
from platform.observability.otel import init_tracer
from platform.observability.metrics import start_prometheus
from platform.observability.logging import setup_logging, get_logger


class DiscoveryWorker(WorkerBase):
    def __init__(self, redis_url=None):
        super().__init__('discovery', redis_url=redis_url)
        self.qm = QueueManager(namespace=self.qm.ns)
        # instantiate local agent for handling
        self.agent_impl = DiscoveryAgent(name='discovery')

    async def process_message(self, message):
        # adapt message to agent impl
        await self.agent_impl.handle_message(message)


async def main():
    # init observability
    setup_logging()
    init_tracer()
    start_prometheus(8000)
    logger = get_logger('example_worker')
    logger.info('starting worker')
    worker = DiscoveryWorker()
    await worker.run()


if __name__ == '__main__':
    asyncio.run(main())
