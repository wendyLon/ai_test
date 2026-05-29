"""Benchmark deduper performance with synthetic data."""
import time
from platform.deduper.engine import DeduperEngine, InMemoryDedupStore

def generate_title(i):
    return f"SEN workshop for kids level {i%10} - session {i}"

def run_benchmark(n=100000):
    store = InMemoryDedupStore()
    engine = DeduperEngine(store=store)

    # Insert n synthetic records
    t0 = time.time()
    for i in range(n):
        rec = {'title_zh_cn': generate_title(i), 'provider_id': i%150, 'schedule_time': f'2026-06-{(i%28)+1}'}
        engine.upsert(rec, record_id=i)
    t1 = time.time()
    insert_time = t1 - t0

    # Query random samples
    t0 = time.time()
    for i in range(1000):
        rec = {'title_zh_cn': generate_title(i*37), 'provider_id': (i*37)%150, 'schedule_time': f'2026-06-{((i*37)%28)+1}'}
        r = engine.check_duplicate(rec)
    t1 = time.time()
    query_time = t1 - t0

    print(f'Inserted {n} records in {insert_time:.2f}s ({n/insert_time:.2f} ops/s)')
    print(f'Ran 1000 duplicate checks in {query_time:.2f}s ({1000/query_time:.2f} ops/s)')

if __name__ == '__main__':
    run_benchmark(10000)  # default smaller for dev machines
