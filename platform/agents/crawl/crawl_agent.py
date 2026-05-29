import asyncio
from typing import Dict, Any
from platform.agents.agent_base import AgentBase
from platform.agents.message import make_message
import os

from playwright.async_api import async_playwright


class CrawlAgent(AgentBase):
    def __init__(self, name='crawl', queue=None, out_queue=None, storage_dir: str = 'data/raw'):
        super().__init__(name, queue)
        self.out_queue = out_queue or asyncio.Queue()
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    async def handle_message(self, msg: Dict[str, Any]):
        payload = msg.get('payload', {})
        url = payload.get('url') or msg.get('url')
        if not url:
            return
        # crawl with Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                resp = await page.goto(url, timeout=30000)
                html = await page.content()
                # save snapshot
                safe = url.replace('://', '_').replace('/', '_')[:200]
                html_path = os.path.join(self.storage_dir, f"{safe}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                screenshot_path = os.path.join(self.storage_dir, f"{safe}.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                out = make_message(agent='dom_analysis', source_agent=self.name, provider_id=msg.get('provider_id'), url=url, payload={'html_path': html_path, 'screenshot': screenshot_path}, metadata={'status_code': resp.status if resp else None})
                await self.out_queue.put(out)
            finally:
                await browser.close()
