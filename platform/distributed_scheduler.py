"""Distributed scheduler handling delayed tasks and periodic jobs.

This scheduler moves due items from the delayed sorted set to agent queues,
and can schedule periodic messages.
"""
import asyncio
import time
from platform.queue_manager import QueueManager


class DistributedScheduler:
    def __init__(self, namespace: str = 'sen', redis_url: str = None, poll_interval: int = 5):
        self.qm = QueueManager(namespace, redis_url)
        self.poll_interval = poll_interval
        self.running = False

    async def run(self):
        self.running = True
        while self.running:
            try:
                moved = self.qm.requeue_due()
                # could emit metrics here
            except Exception:
                pass
            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        self.running = False
