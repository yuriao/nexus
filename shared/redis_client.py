"""
Shared Redis client with connection pooling and pub/sub helpers.
Used across all Nexus services.
"""
import json
import os
import threading
from typing import Any, Callable, Generator

import redis
from redis import ConnectionPool, Redis
from redis.client import PubSub

# ─── Connection Pool ─────────────────────────────────────────────────────────

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
                _pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=20,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    retry_on_timeout=True,
                )
    return _pool


def get_redis() -> Redis:
    """Return a Redis client from the shared connection pool."""
    return Redis(connection_pool=_get_pool())


# ─── Key helpers ─────────────────────────────────────────────────────────────

def report_channel(report_id: str) -> str:
    return f"report:{report_id}"


def scrape_lock_key(company_id: str) -> str:
    return f"scrape_lock:{company_id}"


def rate_limit_key(scraper_name: str) -> str:
    return f"rate_limit:{scraper_name}"


# ─── Pub/Sub helpers ─────────────────────────────────────────────────────────

def publish(channel: str, message: dict) -> int:
    """Publish a JSON-encoded message to a Redis channel. Returns receiver count."""
    r = get_redis()
    return r.publish(channel, json.dumps(message))


def publish_report_event(report_id: str, event_type: str, payload: dict) -> int:
    """Convenience: publish a typed report event."""
    return publish(
        report_channel(report_id),
        {"type": event_type, "report_id": report_id, **payload},
    )


def subscribe_to_channel(channel: str) -> PubSub:
    """Return a PubSub object subscribed to the given channel."""
    r = get_redis()
    ps = r.pubsub(ignore_subscribe_messages=True)
    ps.subscribe(channel)
    return ps


def iter_messages(
    ps: PubSub,
    timeout: float = 1.0,
) -> Generator[dict, None, None]:
    """Yield decoded JSON messages from a PubSub object."""
    for raw in ps.listen():
        if raw and raw.get("type") == "message":
            try:
                yield json.loads(raw["data"])
            except (json.JSONDecodeError, TypeError):
                pass


# ─── Distributed lock ────────────────────────────────────────────────────────

class RedisLock:
    """Simple Redis-backed distributed lock using SET NX PX."""

    def __init__(self, key: str, ttl_seconds: int = 300):
        self.key = key
        self.ttl_ms = ttl_seconds * 1000
        self._r = get_redis()

    def acquire(self) -> bool:
        return bool(self._r.set(self.key, "1", px=self.ttl_ms, nx=True))

    def release(self) -> None:
        self._r.delete(self.key)

    def __enter__(self) -> "RedisLock":
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.key}")
        return self

    def __exit__(self, *_: Any) -> None:
        self.release()
