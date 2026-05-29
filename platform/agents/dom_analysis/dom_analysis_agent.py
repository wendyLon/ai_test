import asyncio
from typing import Dict, Any
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message
from bs4 import BeautifulSoup


class DOMAnalysisAgent(AgentBase):
    def __init__(self, name='dom_analysis', queue=None, out_queue=None):
        super().__init__(name, queue)
        self.out_queue = out_queue or asyncio.Queue()

    async def handle_message(self, msg: Dict[str, Any]):
        payload = msg.get('payload', {})
        html_path = payload.get('html_path')
        if not html_path:
            return
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'lxml')
        # segmentation: reuse extractor logic or simple heuristics
        candidates = []
        # table rows
        for table in soup.find_all('table'):
            for tr in table.find_all('tr'):
                candidates.append(str(tr))
        # list items
        for li in soup.find_all('li'):
            candidates.append(str(li))
        # repeated divs
        sig_count = {}
        for div in soup.find_all(['div','article','section']):
            cls = ' '.join(div.get('class') or [])
            key = (div.name, cls)
            sig_count.setdefault(key, []).append(div)
        for k, elems in sig_count.items():
            if len(elems) >= 3:
                for e in elems:
                    candidates.append(str(e))

        # emit candidate blocks to extraction agent
        for c in candidates:
            out = make_message(agent='event_extraction', source_agent=self.name, provider_id=msg.get('provider_id'), url=msg.get('url'), payload={'block_html': c})
            await self.out_queue.put(out)
