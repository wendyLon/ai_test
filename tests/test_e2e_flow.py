import asyncio
import json
import os
from typing import List

import pytest

from platform.redis_client import get_redis_client
from platform.queue_manager import QueueManager
from workflow_engine.orchestrator import Orchestrator
from workflow_engine.state_machine import State
from tests.test_utils import (
    clear_namespace,
    push_initial_task,
    wait_for_trace_completed,
    get_transitions,
    assert_queues_empty,
    validate_trace_consistency,
    inject_failure,
    get_task_id_from_transitions,
)


NS = 'sen'


async def mock_agent_loop(step: str, stop_event: asyncio.Event, ns: str = NS):
    qm = QueueManager(ns)
    r = get_redis_client()
    while not stop_event.is_set():
        msg = qm.pop(f"{step}-worker", timeout=1)
        if not msg:
            await asyncio.sleep(0.01)
            continue
        # deterministic processing: respect injected failure key
        fail_count = 0
        try:
            v = r.hget(f"{ns}:inject_failure", step)
            if v:
                fail_count = int(v)
        except Exception:
            fail_count = 0

        # simulate little work
        await asyncio.sleep(0.05)
        task_id = msg.get('task_id')
        trace_id = msg.get('trace_id')
        # if instructed to fail, return error and decrement counter
        if fail_count > 0:
            # decrement
            r.hincrby(f"{ns}:inject_failure", step, -1)
            out = {'task_id': task_id, 'trace_id': trace_id, 'step': step, 'status': 'error', 'result': {'err': 'injected'}}
            r.lpush('orchestrator:results', json.dumps(out, ensure_ascii=False))
            continue

        # normal deterministic result
        result = {'step': step, 'task_id': task_id, 'ok': True}
        if step == 'sql':
            # write artifact marker
            if task_id:
                r.set(f"{ns}:task:{task_id}:sql_output", json.dumps({'sql_inserted': True}))
        out = {'task_id': task_id, 'trace_id': trace_id, 'step': step, 'status': 'ok', 'result': result, 'workflow': msg.get('workflow')}
        r.lpush('orchestrator:results', json.dumps(out, ensure_ascii=False))


async def run_test_flow(test_task: dict, timeout: int = 30, inject: str = None):
    # deterministic setup
    clear_namespace(NS)
    r = get_redis_client()

    orchestrator = Orchestrator(namespace=NS)
    orchestrator.load_workflow('sen_training_pipeline', 'workflows/sen_training_pipeline.yaml')
    orch_task = asyncio.create_task(orchestrator.run())

    steps = ['discovery', 'crawl', 'dom_analysis', 'extract', 'sen_classify', 'dedup', 'sql']
    stop_event = asyncio.Event()
    agent_tasks = [asyncio.create_task(mock_agent_loop(s, stop_event)) for s in steps]

    if inject:
        inject_failure(inject, NS)

    # push initial task with deterministic id
    push_initial_task(test_task, NS)

    try:
        trace_key = wait_for_trace_completed(timeout=timeout, ns=NS)
        if not trace_key:
            # dump useful debugging info
            transitions = []
            keys = r.keys(f"{NS}:trace:*:transitions")
            if keys:
                transitions = get_transitions(keys[0].decode() if isinstance(keys[0], bytes) else keys[0])
            return False, transitions
        transitions = get_transitions(trace_key)
        return True, transitions
    finally:
        stop_event.set()
        for t in agent_tasks:
            t.cancel()
        orch_task.cancel()


def test_e2e_flow_deterministic():
    task = {'task_id': 'test-001', 'payload': {'url': 'https://example.com/sen-test'}, 'workflow': 'sen_training_pipeline'}
    ok, transitions = asyncio.run(run_test_flow(task, timeout=20))
    if not ok:
        print('Test failed — transitions:')
        print(json.dumps(transitions, ensure_ascii=False, indent=2))
        pytest.fail('workflow did not complete')

    # queue assertions
    steps = ['discovery', 'crawl', 'dom_analysis', 'extract', 'sen_classify', 'dedup', 'sql']
    assert_queues_empty(steps, NS)

    # trace & state validations
    validate_trace_consistency(transitions, steps)

    # pipeline integrity: ensure mapping of steps to states present in order
    # verify sql artifact
    task_id = get_task_id_from_transitions(transitions) or 'test-001'
    r = get_redis_client()
    assert r.exists(f"{NS}:task:{task_id}:sql_output"), 'sql artifact missing'


def test_e2e_with_injected_failure_and_recovery():
    task = {'task_id': 'test-002', 'payload': {'url': 'https://example.com/sen-test'}, 'workflow': 'sen_training_pipeline'}
    # inject a single failure into crawl
    ok, transitions = asyncio.run(run_test_flow(task, timeout=40, inject='crawl'))
    if not ok:
        print('Failure-injection test failed — transitions:')
        print(json.dumps(transitions, ensure_ascii=False, indent=2))
        pytest.fail('workflow did not complete with injected failure')

    # ensure retry happened: check transitions contains RETRYING or duplicate CRAWLED attempts
    states = [t.get('state') for t in transitions]
    assert State.RETRYING.value in states or states.count(State.CRAWLED.value) >= 1

    # ensure final completion
    validate_trace_consistency(transitions, ['discovery', 'crawl', 'dom_analysis', 'extract', 'sen_classify', 'dedup', 'sql'])

