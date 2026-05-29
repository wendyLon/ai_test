import asyncio
from typing import Dict, Any
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message
from platform.extractor.engine import AdaptiveExtractor
from platform.agents.llm_client import LLMClient


class EventExtractionAgent(AgentBase):
    def __init__(self, name='event_extraction', queue=None, out_queue=None, llm_client: LLMClient = None):
        super().__init__(name, queue)
        self.out_queue = out_queue or asyncio.Queue()
        self.llm = llm_client or LLMClient()
        self.extractor = AdaptiveExtractor(llm_client=self.llm)

    async def handle_message(self, msg: Dict[str, Any]):
        payload = msg.get('payload', {})
        block_html = payload.get('block_html')
        if not block_html:
            return
        # run extractor on block
        results = self.extractor.extract_from_page(block_html, page_url=msg.get('url'))
        # results may be multiple; emit to SEN classification
        for r in results:
            out = make_message(agent='sen_classification', source_agent=self.name, provider_id=msg.get('provider_id'), url=msg.get('url'), payload={'event': r['normalized'], 'confidence': r.get('confidence', {})})
            await self.out_queue.put(out)
