"""
Redis sliding-window rate limiter for scrapers.
Ensures we don't exceed per-domain request limits.
"""
import os
import time

import redis

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
        )
    return _redis_client


RATE_LIMIT_REQUESTS = int(os.environ.get("SCRAPER_RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.environ.get("SCRAPER_RATE_LIMIT_WINDOW_SECONDS", "60"))


def check_rate_limit(scraper_name: str) -> bool:
    """
    Returns True if the request is allowed, False if rate limit exceeded.
    Uses a Redis sorted set with timestamps as scores for sliding window.
    """
    r = _get_redis()
    key = f"rate_limit:{scraper_name}"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    pipe = r.pipeline()
    # Remove expired entries
    pipe.zremrangebyscore(key, "-inf", window_start)
    # Count remaining
    pipe.zcard(key)
    # Add current request
    pipe.zadd(key, {str(now): now})
    # Set key expiry
    pipe.expire(key, RATE_LIMIT_WINDOW * 2)
    results = pipe.execute()

    current_count = results[1]
    return current_count < RATE_LIMIT_REQUESTS


def wait_for_rate_limit(scraper_name: str, poll_interval: float = 1.0) -> None:
    """Block until a request slot is available."""
    while not check_rate_limit(scraper_name):
        time.sleep(poll_interval)
