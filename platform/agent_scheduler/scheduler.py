import asyncio
from typing import Dict, Any, Callable

class AgentTaskScheduler:
    """Async scheduler for agent tasks. Supports queue-based orchestration and retry."""
    def __init__(self):
        self.tasks = []
        self.retry_policy = {}

    def schedule(self, coro: Callable, *args, **kwargs):
        self.tasks.append(asyncio.create_task(coro(*args, **kwargs)))

    async def run_all(self):
        await asyncio.gather(*self.tasks)

    def set_retry_policy(self, agent_name: str, max_retries: int = 3):
        self.retry_policy[agent_name] = max_retries

    async def schedule_with_retry(self, coro_func, *args, max_retries: int = 3, retry_backoff: int = 2, **kwargs):
        attempts = 0
        while attempts <= max_retries:
            try:
                return await coro_func(*args, **kwargs)
            except Exception as e:
                attempts += 1
                await asyncio.sleep(retry_backoff ** attempts)
        raise RuntimeError('Max retries exceeded')
