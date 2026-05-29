"""State machine for workflow orchestration.

Persists transitions to Redis for traceability and replay.
"""
from enum import Enum
import time
import json
import uuid
from typing import Any, Dict, List, Optional
from platform.redis_client import get_redis_client


class State(str, Enum):
    CREATED = 'CREATED'
    DISCOVERED = 'DISCOVERED'
    QUEUED_CRAWL = 'QUEUED_CRAWL'
    CRAWLING = 'CRAWLING'
    CRAWLED = 'CRAWLED'
    DOM_ANALYZING = 'DOM_ANALYZING'
    EXTRACTING = 'EXTRACTING'
    CLASSIFYING_SEN = 'CLASSIFYING_SEN'
    DEDUPING = 'DEDUPING'
    SQL_EXPORTING = 'SQL_EXPORTING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    RETRYING = 'RETRYING'
    DEAD_LETTER = 'DEAD_LETTER'


# allowed transitions map
_TRANSITIONS = {
    State.CREATED: [State.DISCOVERED, State.FAILED],
    State.DISCOVERED: [State.QUEUED_CRAWL, State.FAILED],
    State.QUEUED_CRAWL: [State.CRAWLING, State.FAILED],
    State.CRAWLING: [State.CRAWLED, State.RETRYING, State.FAILED],
    State.CRAWLED: [State.DOM_ANALYZING, State.FAILED],
    State.DOM_ANALYZING: [State.EXTRACTING, State.FAILED],
    State.EXTRACTING: [State.CLASSIFYING_SEN, State.FAILED],
    State.CLASSIFYING_SEN: [State.DEDUPING, State.FAILED],
    State.DEDUPING: [State.SQL_EXPORTING, State.FAILED],
    State.SQL_EXPORTING: [State.COMPLETED, State.FAILED],
    State.RETRYING: [State.CRAWLING, State.FAILED, State.DEAD_LETTER],
}


class StateMachine:
    def __init__(self, task_id: Optional[str] = None, namespace: str = 'sen'):
        self.ns = namespace
        self.r = get_redis_client()
        self.task_id = task_id or str(uuid.uuid4())
        self.trace_id = str(uuid.uuid4()).replace('-', '')
        self.current_state: State = State.CREATED
        # store transitions under key: {ns}:trace:{trace_id}:transitions
        self._transitions_key = f"{self.ns}:trace:{self.trace_id}:transitions"
        self._task_key = f"{self.ns}:task:{self.task_id}"
        # persist initial
        self._record_transition(self.current_state, None, {})

    def _record_transition(self, state: State, agent_result: Optional[Dict[str, Any]], meta: Dict[str, Any]):
        entry = {
            'ts': int(time.time()),
            'state': state.value,
            'agent_result': agent_result or {},
            'meta': meta,
        }
        # push to list for ordered trace
        try:
            self.r.rpush(self._transitions_key, json.dumps(entry, ensure_ascii=False))
        except Exception:
            # best-effort
            pass
        # also update task hash
        try:
            self.r.hset(self._task_key, mapping={'state': state.value, 'trace_id': self.trace_id, 'last_update': int(time.time())})
        except Exception:
            pass

    def can_transition(self, to_state: State) -> bool:
        allowed = _TRANSITIONS.get(self.current_state, [])
        return to_state in allowed

    def transition_to(self, to_state: State, agent_result: Optional[Dict[str, Any]] = None, meta: Dict[str, Any] = {}) -> bool:
        if not self.can_transition(to_state):
            # allow transitions to FAILED from any state
            if to_state != State.FAILED:
                return False
        self.current_state = to_state
        self._record_transition(to_state, agent_result, meta)
        return True

    def rollback(self, steps: int = 1) -> bool:
        # pop last `steps` transitions and set current to previous
        try:
            entries = [json.loads(x) for x in self.r.lrange(self._transitions_key, 0, -1)]
            if len(entries) <= steps:
                return False
            new_current = entries[-1 - steps]
            state_val = new_current.get('state')
            self.current_state = State(state_val)
            self._record_transition(self.current_state, None, {'rollback': True, 'steps': steps})
            return True
        except Exception:
            return False

    def get_trace(self) -> List[Dict[str, Any]]:
        try:
            raw = self.r.lrange(self._transitions_key, 0, -1)
            return [json.loads(x) for x in raw]
        except Exception:
            return []

    def set_retry_policy(self, state: State, retries: int):
        # store per-task retry policies in hash
        key = f"{self._task_key}:retry_policy"
        try:
            self.r.hset(key, mapping={state.value: retries})
        except Exception:
            pass

    def get_retry_count(self, state: State) -> int:
        key = f"{self._task_key}:retries"
        try:
            v = self.r.hget(key, state.value) or b'0'
            return int(v)
        except Exception:
            return 0

    def increment_retry(self, state: State) -> int:
        key = f"{self._task_key}:retries"
        try:
            return self.r.hincrby(key, state.value, 1)
        except Exception:
            return 1
