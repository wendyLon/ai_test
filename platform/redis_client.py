"""Redis client wrapper and helpers."""
import os
import redis
from typing import Optional

def get_redis_client(url: Optional[str] = None) -> redis.Redis:
    redis_url = url or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    return redis.from_url(redis_url, decode_responses=True)
