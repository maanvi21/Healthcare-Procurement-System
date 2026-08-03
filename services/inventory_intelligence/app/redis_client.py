import time
import uuid
from contextlib import contextmanager

import redis

from app.config import settings

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    return _client


class LockAcquisitionError(Exception):
    pass


@contextmanager
def stock_item_lock(stock_item_id: str, timeout_seconds: float = 5.0, ttl_ms: int = 10_000):
    """Redis-backed mutual-exclusion lock keyed by stock item, so two concurrent
    reservation requests for the same SKU can never both read-then-decrement the same
    batch quantity (the classic lost-update race in a reservation system)."""
    client = get_client()
    key = f"inventory:lock:{stock_item_id}"
    token = str(uuid.uuid4())
    deadline = time.monotonic() + timeout_seconds

    acquired = False
    while time.monotonic() < deadline:
        if client.set(key, token, nx=True, px=ttl_ms):
            acquired = True
            break
        time.sleep(0.05)

    if not acquired:
        raise LockAcquisitionError(f"Could not acquire lock for stock item {stock_item_id}")

    try:
        yield
    finally:
        # only release if we still hold it (best-effort; ttl is the real safety net)
        if client.get(key) == token:
            client.delete(key)
