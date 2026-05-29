import asyncio
from typing import Any, Dict

class AgentBase:
    """Base class for all agents. Implements async queue-based execution and JSON message passing."""
    def __init__(self, name: str, queue: asyncio.Queue = None):
        self.name = name
        self.queue = queue or asyncio.Queue()
        self.running = False

    async def run(self):
        self.running = True
        while self.running:
            msg = await self.queue.get()
            try:
                await self.handle_message(msg)
            except Exception as e:
                await self.on_error(msg, e)
            finally:
                self.queue.task_done()

    async def handle_message(self, msg: Dict[str, Any]):
        raise NotImplementedError()

    async def on_error(self, msg: Dict[str, Any], exc: Exception):
        print(f"[{self.name}] Error: {exc}")

    async def stop(self):
        self.running = False
