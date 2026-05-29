# Migration Plan: In-memory → Redis Queue

Steps:

1. Deploy Redis and ensure network accessibility.
2. Start QueueManager/WorkerBase in a side-by-side mode: run Redis-enabled workers while keeping in-memory agents running.
3. Implement a compatibility bridge: a small adapter that drains in-memory queues and pushes tasks into Redis queues (provided in `platform/queue_bridge.py`).
4. Gradually switch agents to Redis worker processes; monitor queue lengths and DLQ.
5. Decommission in-memory queues once no tasks remain.

Fallback mode:
- `QueueManager` can be used in a "local" mode by pointing to a local Redis instance or by providing a shim that reads from in-memory queues.

Idempotency:
- Ensure tasks include stable `task_id` so replay does not create duplicates; dedup engine is critical.

Recovery:
- Use `distributed_scheduler` to requeue delayed tasks on restart.

