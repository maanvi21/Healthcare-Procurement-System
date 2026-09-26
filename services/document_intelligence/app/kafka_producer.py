import json
import logging
from datetime import datetime, timezone

try:
    from kafka import KafkaProducer
except Exception:
    KafkaProducer = None

from app.config import settings

logger = logging.getLogger(__name__)

_producer = None


def _get_producer():
    global _producer
    if KafkaProducer is None:
        return None
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                retries=3,
            )
        except Exception as e:
            logger.warning("Could not initialize KafkaProducer: %s", e)
            _producer = None
    return _producer


def publish_event(topic: str, key: str, data: dict) -> None:
    envelope = {
        "event": topic,
        "data": data,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    producer = _get_producer()
    if producer:
        try:
            producer.send(topic, key=key, value=envelope)
            producer.flush()
        except Exception as e:
            logger.warning("Error publishing Kafka event to %s: %s", topic, e)

