import json
import time
from typing import Dict, Any, List, Optional
from platform.redis_client import get_redis_client
from platform.queue_manager import QueueManager
from workflow_engine.state_machine import State

NS = 'sen'


def clear_namespace(ns: str = NS):
    r = get_redis_client()
    # delete keys matching ns:* (best-effort, careful in prod)
    for k in r.keys(f"{ns}:*"):
        try:
            r.delete(k)
        except Exception:
            pass


def push_initial_task(task: Dict[str, Any], ns: str = NS):
    r = get_redis_client()
    r.lpush('orchestrator:input', json.dumps(task, ensure_ascii=False))


def wait_for_trace_completed(timeout: int = 30, ns: str = NS, poll_interval: float = 0.2) -> Optional[str]:
    r = get_redis_client()
    started = time.time()
    pattern = f"{ns}:trace:*:transitions"
    while time.time() - started < timeout:
        keys = r.keys(pattern)
        if keys:
            for tk in keys:
                vals = r.lrange(tk, 0, -1)
                if not vals:
                    continue
                last = json.loads(vals[-1])
                if last.get('state') == State.COMPLETED.value:
                    return tk.decode() if isinstance(tk, bytes) else tk
        time.sleep(poll_interval)
    return None


def get_transitions(trace_key: str) -> List[Dict[str, Any]]:
    r = get_redis_client()
    vals = r.lrange(trace_key, 0, -1)
    return [json.loads(x) for x in vals]


def assert_queues_empty(steps: List[str], ns: str = NS):
    qm = QueueManager(ns)
    # check main orchestrator queues
    r = get_redis_client()
    assert r.llen('orchestrator:input') == 0
    assert r.llen('orchestrator:results') == 0
    for s in steps:
        q = f"{s}-worker"
        assert qm.len(q) == 0, f"queue {q} not empty"
    # check retry/delayed/deadletter conventions if used
    # best-effort: check keys
    for k in r.keys(f"{ns}:dlq:*"):
        assert False, f"dead letter not empty: {k}"


def validate_trace_consistency(transitions: List[Dict[str, Any]], required_steps: List[str]):
    # Validate trace_id exists and ordering
    assert transitions, 'no transitions'
    trace_states = [t.get('state') for t in transitions]
    # ensure final state is COMPLETED
    assert trace_states[-1] == State.COMPLETED.value
    # map required steps to states
    step_state_map = {
        'discovery': State.DISCOVERED.value,
        'crawl': State.CRAWLED.value,
        'dom_analysis': State.DOM_ANALYZING.value,
        'extract': State.EXTRACTING.value,
        'sen_classify': State.CLASSIFYING_SEN.value,
        'dedup': State.DEDUPING.value,
        'sql': State.SQL_EXPORTING.value,
    }
    seen = []
    for s in required_steps:
        st = step_state_map.get(s)
        assert st in trace_states, f"state {st} missing in trace"
        seen.append(st)
    # ensure ordering: indices increasing
    indices = [trace_states.index(x) for x in seen]
    assert indices == sorted(indices), 'step ordering incorrect'
    # no duplicates of these key states
    for st in seen:
        assert trace_states.count(st) == 1, f'duplicate state {st}'


def inject_failure(step: str, ns: str = NS):
    r = get_redis_client()
    # set a key agent reads to fail once
    r.hset(f"{ns}:inject_failure", step, 1)


def get_task_id_from_transitions(transitions: List[Dict[str, Any]]) -> Optional[str]:
    for t in transitions:
        ar = t.get('agent_result') or {}
        if isinstance(ar, dict):
            maybe = ar.get('task_id') or ar.get('agent_result', {}).get('task_id')
            if maybe:
                return maybe
    return None
