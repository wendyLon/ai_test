"""CLI tools to inspect workflow traces and export logs."""
import argparse
import json
from workflow_engine.state_machine import StateMachine
from platform.observability.debug_tools import find_tasks_by_trace


def view_trace(trace_id: str, namespace: str = 'sen'):
    matches = find_tasks_by_trace(namespace, trace_id)
    if not matches:
        print('No tasks found for trace:', trace_id)
        return
    for m in matches:
        meta = m['meta']
        task_id = meta.get('task_id')
        sm = StateMachine(task_id=task_id, namespace=namespace)
        sm.trace_id = trace_id
        trans = sm.get_trace()
        print(json.dumps(trans, ensure_ascii=False, indent=2))


def export_trace(trace_id: str, out: str, namespace: str = 'sen'):
    matches = find_tasks_by_trace(namespace, trace_id)
    if not matches:
        print('No tasks found for trace:', trace_id)
        return
    all_trans = []
    for m in matches:
        meta = m['meta']
        task_id = meta.get('task_id')
        sm = StateMachine(task_id=task_id, namespace=namespace)
        sm.trace_id = trace_id
        all_trans.extend(sm.get_trace())
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_trans, f, ensure_ascii=False, indent=2)
    print('exported to', out)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd')
    v = sub.add_parser('view')
    v.add_argument('trace_id')
    e = sub.add_parser('export')
    e.add_argument('trace_id')
    e.add_argument('out')
    args = p.parse_args()
    if args.cmd == 'view':
        view_trace(args.trace_id)
    elif args.cmd == 'export':
        export_trace(args.trace_id, args.out)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
