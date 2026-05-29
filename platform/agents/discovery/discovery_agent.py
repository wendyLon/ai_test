import asyncio
from typing import Dict, Any, List
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message


class DiscoveryAgent(AgentBase):
    """Discover event pages, calendars, PDFs and emit crawl tasks.

    Emits messages to the crawl agent queue with payload: {'type':'crawl','url':..., 'depth':...}
    """
    def __init__(self, name='discovery', queue=None, out_queue=None):
        super().__init__(name, queue)
        self.out_queue = out_queue or asyncio.Queue()

    async def handle_message(self, msg: Dict[str, Any]):
        # msg.payload expected to include starting URL(s)
        seeds = msg.get('payload', {}).get('seeds', [])
        provider_id = msg.get('provider_id')
        for url in seeds:
            # classify priority (simple heuristic)
            priority = 'high' if 'events' in url or 'calendar' in url else 'normal'
            task = make_message(agent='crawl', source_agent=self.name, provider_id=provider_id, url=url, payload={'type':'crawl','url':url,'depth':0}, metadata={'discovered_by':'discovery'}, priority=priority)
            await self.out_queue.put(task)

    async def discover_from_file(self, urls_file: str):
        with open(urls_file, 'r', encoding='utf-8') as f:
            seeds = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        msg = make_message(agent=self.name, source_agent='system', payload={'seeds': seeds})
        await self.handle_message(msg)
