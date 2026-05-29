"""Standard JSON message protocol and helpers for inter-agent communication."""
from typing import Dict, Any
from datetime import datetime
import uuid
import json

BASE_MESSAGE_KEYS = [
    "task_id","agent","source_agent","timestamp","provider_id","url","payload","metadata","retry_count","priority","status","trace_id"
]

def make_message(agent: str, source_agent: str, provider_id: Any = None, url: str = '', payload: Dict = None, metadata: Dict = None, priority: str = 'normal') -> Dict:
    payload = payload or {}
    metadata = metadata or {}
    msg = {
        "task_id": str(uuid.uuid4()),
        "agent": agent,
        "source_agent": source_agent,
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "provider_id": provider_id,
        "url": url,
        "payload": payload,
        "metadata": metadata,
        "retry_count": 0,
        "priority": priority,
        "status": "pending",
        "trace_id": str(uuid.uuid4())
    }
    return msg

def serialize(msg: Dict) -> str:
    return json.dumps(msg, ensure_ascii=False)

def deserialize(s: str) -> Dict:
    return json.loads(s)
