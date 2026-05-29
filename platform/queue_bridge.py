"""Bridge to migrate in-memory queues to Redis queues during transition.

This module reads from existing in-memory asyncio queues (if provided) and pushes
messages into Redis via QueueManager. Use during migration window.
"""
import asyncio
from typing import Dict
from platform.queue_manager import QueueManager


async def bridge_queue(agent_name: str, in_queue: asyncio.Queue, namespace: str = 'sen'):
    qm = QueueManager(namespace)
    while True:
        msg = await in_queue.get()
        qm.push(agent_name, msg, priority=msg.get('priority','normal'))
        in_queue.task_done()
