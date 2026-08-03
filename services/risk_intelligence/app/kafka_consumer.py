"""Background consumer: auto-runs a risk assessment whenever vendor_intelligence
publishes `vendor.onboarded` or `vendor.updated`, using default operational-signal
values (no live logistics/ERP feed exists in this build — see features.py). This keeps
every vendor's risk_band fresh without a human having to remember to trigger it."""
import json
import logging
import threading

from app.config import settings
from app.db import SessionLocal
from app.service import assess_vendor

logger = logging.getLogger("risk_intelligence.kafka_consumer")

TOPICS = ["vendor.onboarded", "vendor.updated"]


def _handle_vendor_event(data: dict) -> None:
    vendor_id = data.get("vendor_id")
    if not vendor_id:
        return
    db = SessionLocal()
    try:
        assess_vendor(db, vendor_id, operational_signals={})
        logger.info("Assessed risk for vendor %s", vendor_id)
    except Exception:
        logger.exception("Risk assessment failed for vendor %s", vendor_id)
    finally:
        db.close()


def _consume_loop():
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="risk-intelligence",
    )
    for message in consumer:
        try:
            envelope = message.value
            if envelope.get("event") in TOPICS:
                _handle_vendor_event(envelope.get("data", {}))
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread() -> None:
    threading.Thread(target=_consume_loop, daemon=True, name="risk-vendor-consumer").start()
