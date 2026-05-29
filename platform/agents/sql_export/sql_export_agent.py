import asyncio
from typing import Dict, Any
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message
from platform.exporter.sql_exporter import generate_upsert
import os


class SQLExportAgent(AgentBase):
    def __init__(self, name='sql_export', queue=None, out_queue=None, out_dir: str = 'data/sql'):
        super().__init__(name, queue)
        self.out_queue = out_queue or asyncio.Queue()
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)

    async def handle_message(self, msg: Dict[str, Any]):
        payload = msg.get('payload', {})
        event = payload.get('event')
        if not event:
            return
        decision = payload.get('decision', 'insert')
        # Map event fields to sys_training columns (simple mapping here)
        record = {
            'web_url': event.get('web_url'),
            'title_zh_cn': event.get('title_zh_cn') or event.get('title_zh_tw') or event.get('title_en_us'),
            'description_zh_cn': event.get('description_zh_cn'),
            'fee': event.get('fee'),
            'currency': event.get('currency','HKD'),
            'provider_id': payload.get('provider_id')
        }
        sql, params = generate_upsert('sys_training', record, unique_keys=['web_url'])
        fname = os.path.join(self.out_dir, f"{payload.get('fingerprint','unknown')}.sql")
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(sql + '\n')
        # emit DB import task or log
        out = make_message(agent='system', source_agent=self.name, provider_id=msg.get('provider_id'), url=msg.get('url'), payload={'sql_file': fname, 'decision': decision})
        await self.out_queue.put(out)
