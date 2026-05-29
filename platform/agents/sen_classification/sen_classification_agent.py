import asyncio
from typing import Dict, Any
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message
from platform.agents.llm_client import LLMClient


class SENClassificationAgent(AgentBase):
    def __init__(self, name='sen_classification', queue=None, out_queue=None, llm_client: LLMClient = None):
        super().__init__(name, queue)
        self.out_queue = out_queue or asyncio.Queue()
        self.llm = llm_client or LLMClient()

    async def handle_message(self, msg: Dict[str, Any]):
        payload = msg.get('payload', {})
        event = payload.get('event')
        if not event:
            return
        # call LLM classify (mock or real)
        text = (event.get('title_zh_cn','') or '') + '\n' + (event.get('description_zh_cn','') or '')
        cls = self.llm.classify(text, task='sen_relevance')
        # augment event
        event['sen_metadata'] = cls
        out = make_message(agent='dedup', source_agent=self.name, provider_id=msg.get('provider_id'), url=msg.get('url'), payload={'event': event, 'confidence': payload.get('confidence', {})})
        await self.out_queue.put(out)
