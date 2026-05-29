import asyncio
from typing import Dict, Any
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message
from platform.deduper.engine import DeduperEngine, InMemoryDedupStore


class DedupAgent(AgentBase):
    def __init__(self, name='dedup', queue=None, out_queue=None, store=None):
        super().__init__(name, queue)
        self.out_queue = out_queue or asyncio.Queue()
        self.store = store or InMemoryDedupStore()
        self.engine = DeduperEngine(store=self.store)

    async def handle_message(self, msg: Dict[str, Any]):
        payload = msg.get('payload', {})
        event = payload.get('event')
        if not event:
            return
        res = self.engine.check_duplicate(event)
        decision = 'insert' if not res['is_duplicate'] else 'update'
        # upsert into dedup index
        fp = self.engine.upsert(event)
        out = make_message(agent='sql_export', source_agent=self.name, provider_id=msg.get('provider_id'), url=msg.get('url'), payload={'event': event, 'dedup': res, 'fingerprint': fp, 'decision': decision})
        await self.out_queue.put(out)
