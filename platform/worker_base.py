"""Worker base for Redis-backed agents.

Agents should subclass WorkerBase and implement `process_message(self, message)`.

WorkerBase handles:
- BRPOPLPUSH from main queue to processing list
- ack on success (LREM)
- move to DLQ or schedule retry on failure
- task state persistence in Redis hash
"""
import time
import json
import traceback
from typing import Dict, Any, Optional
from platform.queue_manager import QueueManager
from platform.redis_client import get_redis_client
from platform.observability.otel import get_tracer, extract_context_from_message, inject_trace_into_message
from platform.observability.metrics import record_processing_latency, record_failure
from platform.observability.logging import get_logger
import time


class WorkerBase:
    def __init__(self, agent_name: str, namespace: str = 'sen', redis_url: Optional[str] = None, max_retries: int = 5):
        self.agent = agent_name
        self.qm = QueueManager(namespace, redis_url)
        self.r = get_redis_client(redis_url)
        self.running = False
        self.max_retries = max_retries

    def _task_state_key(self, task_id: str) -> str:
        return f"{self.qm.ns}:task:{task_id}"

    def persist_task_state(self, message: Dict[str, Any], state: str, reason: str = ''):
        key = self._task_state_key(message.get('task_id'))
        data = {
            'state': state,
            'last_update': int(time.time()),
            'retry_count': message.get('retry_count', 0),
            'reason': reason
        }
        # include trace_id and payload snapshot for debugging/replay
        data['trace_id'] = message.get('trace_id')
        try:
            data['message'] = message
        except Exception:
            data['message'] = {}
        self.r.hset(key, mapping={k: json.dumps(v, ensure_ascii=False) for k, v in data.items()})

    async def run(self):
        self.running = True
        while self.running:
            # pop message reliably
            msg = self.qm.pop(self.agent, timeout=5)
            if not msg:
                # check delayed requeue periodically
                try:
                    self.qm.requeue_due()
                except Exception:
                    pass
                continue
            task_id = msg.get('task_id')
            # observability: start span and record processing latency
            logger = get_logger(f'worker.{self.agent}')
            tracer = get_tracer()
            start_ts = time.time()
            try:
                # extract context if any and start span
                ctx = extract_context_from_message(msg)
                with tracer.start_as_current_span(f"{self.agent}.process", context=ctx):
                    self.persist_task_state(msg, 'running')
                    result = await self.process_message(msg)
                    # on success ack and mark completed
                    self.qm.ack(self.agent, msg)
                    self.persist_task_state(msg, 'completed')
            except Exception as e:
                # failure handling
                tb = traceback.format_exc()
                msg['retry_count'] = msg.get('retry_count', 0) + 1
                self.persist_task_state(msg, 'failed', reason=str(e))
                record_failure(self.agent, msg.get('provider_id'))
                logger.error('task_failed', extra={'task_id': msg.get('task_id'), 'error': str(e), 'trace': msg.get('trace_id')})
                if msg['retry_count'] > self.max_retries:
                    self.qm.move_to_dlq(self.agent, msg, reason=str(e))
                else:
                    # schedule retry with exponential backoff
                    delay = 2 ** (msg['retry_count'] - 1)
                    self.qm.retry_later(self.agent, msg, delay)
            finally:
                latency = time.time() - start_ts
                try:
                    record_processing_latency(self.agent, latency)
                except Exception:
                    pass

    async def stop(self):
        self.running = False

    async def process_message(self, message: Dict[str, Any]) -> Any:
        raise NotImplementedError()
