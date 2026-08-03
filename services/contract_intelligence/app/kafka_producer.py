import json
from datetime import datetime, timezone

from kafka import KafkaProducer

from app.config import settings

_producer: KafkaProducer | None = None


def _get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            retries=3,
        )
    return _producer


def publish_event(topic: str, key: str, data: dict) -> None:
    envelope = {"event": topic, "data": data, "occurred_at": datetime.now(timezone.utc).isoformat()}
    producer = _get_producer()
    producer.send(topic, key=key, value=envelope)
    producer.flush()
