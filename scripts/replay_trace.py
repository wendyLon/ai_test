"""Replay workflow by trace_id: prints transitions and optionally re-enqueues the initial task."""
import argparse
import json
from workflow_engine.state_machine import StateMachine
from platform.observability.debug_tools import find_tasks_by_trace, replay_task


def print_trace(trace_id: str, namespace: str = 'sen'):
    # attempt to find task(s) by scanning /trace key
    matches = find_tasks_by_trace(namespace, trace_id)
    if not matches:
        print('No tasks found for trace:', trace_id)
        return
    for m in matches:
        print('Task key:', m['key'])
        meta = m['meta']
        # load transitions
        # transitions stored under {ns}:trace:{trace_id}:transitions
        sm = StateMachine(task_id=meta.get('task_id'), namespace=namespace)
        sm.trace_id = trace_id
        trans = sm.get_trace()
        for t in trans:
            print(json.dumps(t, ensure_ascii=False))


def replay(trace_id: str, namespace: str = 'sen'):
    matches = find_tasks_by_trace(namespace, trace_id)
    if not matches:
        print('No tasks found for trace:', trace_id)
        return
    # replay by re-enqueueing the first task payload
    for m in matches:
        meta = m['meta']
        task_msg = meta.get('message')
        if task_msg:
            ok = replay_task(namespace, task_msg)
            print('Re-enqueued:', ok)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('trace_id')
    p.add_argument('--replay', action='store_true')
    args = p.parse_args()
    print_trace(args.trace_id)
    if args.replay:
        replay(args.trace_id)


if __name__ == '__main__':
    main()
