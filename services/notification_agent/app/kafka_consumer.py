"""Background Kafka consumer for notification_agent.

Subscribes to existing MediSource topics (see scripts/init-kafka-topics.sh) and renders
matching email templates. Delivery is marked simulated if SendGrid is not configured.

Topics consumed are all event topics currently published by the platform. Each has an
email template so uploads, reviews, vendor changes, approvals, risk and inventory events,
and contract lifecycle updates produce an email notification.
"""
import json
import logging
import threading

from kafka import KafkaConsumer

from app.config import settings
from app.db import SessionLocal
from app.service import handle_event
from app.topics import TOPIC_PATTERN

logger = logging.getLogger("notification_agent.kafka_consumer")


def _consume_loop():
    consumer = KafkaConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="notification-agent",
    )
    consumer.subscribe(pattern=TOPIC_PATTERN)
    for message in consumer:
        try:
            envelope = message.value or {}
            event = envelope.get("event") or message.topic
            data = envelope.get("data", {})
            if not isinstance(data, dict):
                data = {}
            db = SessionLocal()
            try:
                sent = handle_event(
                    db,
                    event,
                    data,
                    event_key=f"{message.topic}:{message.partition}:{message.offset}",
                )
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
