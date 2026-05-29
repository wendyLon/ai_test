"""Simulate end-to-end agent pipeline using in-memory queues.

Run this script to see messages flow between agents and example retries.
"""
import asyncio
from platform.agents.discovery.discovery_agent import DiscoveryAgent
from platform.agents.crawl.crawl_agent import CrawlAgent
from platform.agents.dom_analysis.dom_analysis_agent import DOMAnalysisAgent
from platform.agents.event_extraction.event_extraction_agent import EventExtractionAgent
from platform.agents.sen_classification.sen_classification_agent import SENClassificationAgent
from platform.agents.dedup.dedup_agent import DedupAgent
from platform.agents.sql_export.sql_export_agent import SQLExportAgent
from platform.agents.retry_recovery.retry_recovery_agent import RetryRecoveryAgent
from platform.agents.message import make_message


async def main():
    # create queues
    q_discover = asyncio.Queue()
    q_crawl = asyncio.Queue()
    q_dom = asyncio.Queue()
    q_extract = asyncio.Queue()
    q_sen = asyncio.Queue()
    q_dedup = asyncio.Queue()
    q_sql = asyncio.Queue()
    q_retry = asyncio.Queue()

    # create agents
    discovery = DiscoveryAgent(queue=q_discover, out_queue=q_crawl)
    crawl = CrawlAgent(queue=q_crawl, out_queue=q_dom)
    dom = DOMAnalysisAgent(queue=q_dom, out_queue=q_extract)
    extract = EventExtractionAgent(queue=q_extract, out_queue=q_sen)
    sen = SENClassificationAgent(queue=q_sen, out_queue=q_dedup)
    dedup = DedupAgent(queue=q_dedup, out_queue=q_sql)
    sql = SQLExportAgent(queue=q_sql, out_queue=asyncio.Queue())
    retry = RetryRecoveryAgent(queue=asyncio.Queue(), retry_queue=q_retry)

    # schedule agents
    tasks = [
        asyncio.create_task(discovery.run()),
        asyncio.create_task(crawl.run()),
        asyncio.create_task(dom.run()),
        asyncio.create_task(extract.run()),
        asyncio.create_task(sen.run()),
        asyncio.create_task(dedup.run()),
        asyncio.create_task(sql.run()),
        asyncio.create_task(retry.run()),
    ]

    # feed discovery with a seed
    seed_msg = make_message(agent='discovery', source_agent='system', provider_id=1, payload={'seeds': ['https://example.org/events']})
    await q_discover.put(seed_msg)

    # run for a short time
    await asyncio.sleep(5)

    # stop agents
    for a in [discovery, crawl, dom, extract, sen, dedup, sql, retry]:
        await a.stop()
    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == '__main__':
    asyncio.run(main())
