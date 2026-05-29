"""Redis-backed queue manager supporting reliable queues, delayed retry and DLQ."""
import json
import time
from typing import Optional, Dict, Any, List
from platform.redis_client import get_redis_client
from platform.observability.otel import inject_trace_into_message


class QueueManager:
    def __init__(self, namespace: str = 'sen', redis_url: Optional[str] = None):
        self.ns = namespace
        self.r = get_redis_client(redis_url)

    def _qname(self, agent: str) -> str:
        return f"{self.ns}:queue:{agent}"

    def _processing_name(self, agent: str) -> str:
        return f"{self.ns}:processing:{agent}"

    def _dlq_name(self, agent: str) -> str:
        return f"{self.ns}:dlq:{agent}"

    def _delayed_key(self) -> str:
        return f"{self.ns}:delayed"

    def push(self, agent: str, message: Dict[str, Any], priority: str = 'normal') -> None:
        key = self._qname(agent)
        # inject current trace context into message metadata for distributed tracing
        try:
            message = inject_trace_into_message(message)
        except Exception:
            pass
        payload = json.dumps(message, ensure_ascii=False)
        if priority == 'high':
            # LPUSH high priority to left
            self.r.lpush(key, payload)
        else:
            self.r.rpush(key, payload)

    def pop(self, agent: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Atomically pop from queue to processing list (reliable pop).

        Uses BRPOPLPUSH semantics: pop from queue and push into processing list.
        Returns the message dict or None on timeout.
        """
        q = self._qname(agent)
        proc = self._processing_name(agent)
        item = self.r.brpoplpush(q, proc, timeout=timeout)
        if item:
            try:
                return json.loads(item)
            except Exception:
                return None
        return None

    def ack(self, agent: str, message: Dict[str, Any]) -> None:
        """Acknowledge processing of a message: remove from processing list."""
        proc = self._processing_name(agent)
        raw = json.dumps(message, ensure_ascii=False)
        # LREM to remove one occurrence
        self.r.lrem(proc, 1, raw)

    def move_to_dlq(self, agent: str, message: Dict[str, Any], reason: str = '') -> None:
        dlq = self._dlq_name(agent)
        msg = dict(message)
        msg.setdefault('metadata', {})
        msg['metadata']['dlq_reason'] = reason
        msg['metadata']['dlq_at'] = int(time.time())
        self.r.rpush(dlq, json.dumps(msg, ensure_ascii=False))
        # also ack from processing
        self.ack(agent, message)

    def retry_later(self, agent: str, message: Dict[str, Any], delay_seconds: int) -> None:
        """Schedule message to be requeued after delay via sorted set."""
        key = self._delayed_key()
        score = int(time.time()) + delay_seconds
        item = json.dumps({'agent': agent, 'message': message}, ensure_ascii=False)
        self.r.zadd(key, {item: score})
        # ack current processing
        self.ack(agent, message)

    def requeue_due(self) -> int:
        """Move due delayed items back into their queues. Returns number moved."""
        key = self._delayed_key()
        now = int(time.time())
        items = self.r.zrangebyscore(key, 0, now)
        for it in items:
            try:
                data = json.loads(it)
                agent = data.get('agent')
                message = data.get('message')
                # push back to agent queue
                self.push(agent, message, priority=message.get('priority','normal'))
            except Exception:
                continue
            self.r.zrem(key, it)
        return len(items)

    def len(self, agent: str) -> int:
        return self.r.llen(self._qname(agent))

    def processing_len(self, agent: str) -> int:
        return self.r.llen(self._processing_name(agent))

    def dlq_len(self, agent: str) -> int:
        return self.r.llen(self._dlq_name(agent))

    def peek_processing(self, agent: str, count: int = 10) -> List[Dict[str, Any]]:
        raw = self.r.lrange(self._processing_name(agent), 0, count-1)
        out = []
        for r in raw:
            try:
                out.append(json.loads(r))
            except Exception:
                continue
        return out
