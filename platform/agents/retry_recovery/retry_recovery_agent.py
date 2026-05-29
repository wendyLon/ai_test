import asyncio
from typing import Dict, Any
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message
import math


class RetryRecoveryAgent(AgentBase):
    def __init__(self, name='retry_recovery', queue=None, retry_queue=None, dlq=None, max_retries: int = 5):
        super().__init__(name, queue)
        self.retry_queue = retry_queue or asyncio.Queue()
        self.dlq = dlq or asyncio.Queue()
        self.max_retries = max_retries

    async def handle_message(self, msg: Dict[str, Any]):
        # message is expected to be a failure notice or retry request
        retry_count = msg.get('retry_count', 0)
        if retry_count >= self.max_retries:
            await self.dlq.put(msg)
            return
        # exponential backoff schedule
        backoff = int(math.pow(2, retry_count))
        await asyncio.sleep(backoff)
        msg['retry_count'] = retry_count + 1
        # re-enqueue to original agent queue if specified in metadata
        target_agent = msg.get('metadata', {}).get('target_agent')
        if target_agent and isinstance(target_agent, asyncio.Queue):
            await target_agent.put(msg)
        else:
            # fallback: push to retry_queue for manual routing
            await self.retry_queue.put(msg)
