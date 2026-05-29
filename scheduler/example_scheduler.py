"""Example scheduler using APScheduler to run weekly crawls."""
from apscheduler.schedulers.background import BackgroundScheduler
from platform.crawler.crawler import Crawler
import time

def weekly_job():
    c = Crawler(out_dir='data/raw')
    # In real use, dispatch to queue or run in background workers
    import asyncio
    asyncio.run(c.run_from_file('url.txt'))

def start_scheduler():
    sched = BackgroundScheduler()
    # weekly at Monday 03:00
    sched.add_job(weekly_job, 'cron', day_of_week='mon', hour=3, minute=0, id='weekly_crawl')
    sched.start()
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()

if __name__ == '__main__':
    start_scheduler()
