import asyncio
import os
from pathlib import Path
from typing import List

# Minimal Playwright-based crawler skeleton
from playwright.async_api import async_playwright

class Crawler:
    def __init__(self, out_dir: str = "./data", concurrency: int = 3):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.concurrency = concurrency

    async def fetch(self, url: str) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                resp = await page.goto(url, timeout=30000)
                html = await page.content()
                screenshot = self.out_dir / (self._safe_name(url) + '.png')
                await page.screenshot(path=str(screenshot), full_page=True)
                return {
                    'url': url,
                    'status': resp.status if resp else None,
                    'html': html,
                    'screenshot': str(screenshot)
                }
            finally:
                await browser.close()

    def _safe_name(self, url: str) -> str:
        return url.replace('://', '_').replace('/', '_').replace('?', '_')[:200]

    async def run_from_file(self, urls_file: str):
        tasks = []
        with open(urls_file, 'r', encoding='utf-8') as f:
            for line in f:
                u = line.strip()
                if not u or u.startswith('#'): 
                    continue
                tasks.append(self.fetch(u))
        return await asyncio.gather(*tasks)

if __name__ == '__main__':
    import sys
    in_file = sys.argv[1] if len(sys.argv) > 1 else 'url.txt'
    c = Crawler(out_dir='data/raw')
    asyncio.run(c.run_from_file(in_file))
