"""Background Kafka consumer for notification_agent.

Subscribes to existing MediSource topics (see scripts/init-kafka-topics.sh) and
renders matching DB templates into multi-channel stub notifications.

Topics consumed (all already used elsewhere in this codebase):
  vendor.onboarded, documents.processed, approval.approved, approval.rejected,
  approval.escalated, risk.assessed, inventory.backorder, contract.signed
"""
import json
import logging
import threading

from kafka import KafkaConsumer

from app.config import settings
from app.db import SessionLocal
from app.service import handle_event

logger = logging.getLogger("notification_agent.kafka_consumer")

TOPICS = [
    "vendor.onboarded",
    "documents.processed",
    "approval.approved",
    "approval.rejected",
    "approval.escalated",
    "risk.assessed",
    "inventory.backorder",
    "contract.signed",
]


def _consume_loop():
    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="notification-agent",
    )
    for message in consumer:
        try:
            envelope = message.value or {}
            event = envelope.get("event") or message.topic
            data = envelope.get("data", {})
            if not isinstance(data, dict):
                data = {}
            db = SessionLocal()
            try:
                sent = handle_event(db, event, data)
                if sent:
                    logger.info(
                        "Emitted %d notification(s) for event %s",
                        len(sent),
                        event,
                    )
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread() -> None:
    thread = threading.Thread(target=_consume_loop, daemon=True, name="notification-event-consumer")
    thread.start()
