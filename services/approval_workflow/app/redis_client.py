import hashlib
import json

import redis

from app.config import settings

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    return _client


def is_duplicate_submission(department: str, vendor_id: str | None, total_value: float, items: list[dict]) -> bool:
    """SETNX-based dedup: the same {department, vendor, value, items} submitted twice
    within the dedup window is treated as an accidental double-submit (double-click,
    retried request) rather than a genuine second request."""
    fingerprint = hashlib.sha256(
        json.dumps({"department": department, "vendor_id": vendor_id, "total_value": total_value, "items": items}, sort_keys=True).encode()
    ).hexdigest()
    key = f"procreq:dedup:{fingerprint}"
    client = get_client()
    was_set = client.set(key, "1", nx=True, ex=settings.dedup_window_seconds)
    return not was_set
