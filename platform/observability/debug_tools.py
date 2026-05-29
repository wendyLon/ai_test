"""Debug tools: replay pipeline by trace_id and visualize agent chain."""
from platform.redis_client import get_redis_client
from typing import List, Dict, Any
import json


def find_tasks_by_trace(ns: str, trace_id: str) -> List[Dict[str, Any]]:
    r = get_redis_client()
    pattern = f"{ns}:task:*"
    cursor = '0'
    out = []
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=1000)
        for k in keys:
            try:
                data = r.hgetall(k)
                # data contains JSON values
                if data:
                    meta = {kk: json.loads(v) for kk, v in data.items() if v}
                    if meta.get('trace_id') == trace_id or meta.get('trace_id', '') == trace_id:
                        out.append({'key': k, 'meta': meta})
            except Exception:
                continue
        if cursor == '0':
            break
    return out


def replay_task(ns: str, task_payload: Dict[str, Any]) -> bool:
    # Push message back to its agent queue
    from platform.queue_manager import QueueManager
    qm = QueueManager(namespace=ns)
    agent = task_payload.get('agent')
    if not agent:
        return False
    qm.push(agent, task_payload)
    return True
