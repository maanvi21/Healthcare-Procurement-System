"""Background Kafka consumer: updates a vendor's risk_band whenever risk_intelligence
publishes a fresh assessment. Runs as a daemon thread started from main.py's startup
event so the FastAPI app and the consumer share the process but not the request loop."""
import json
import logging
import threading

from kafka import KafkaConsumer

from app.config import settings
from app.db import SessionLocal
from app.models import RiskBand, Vendor

logger = logging.getLogger("vendor_intelligence.kafka_consumer")

TOPICS = ["risk.assessed"]


def _handle_risk_assessed(data: dict) -> None:
    vendor_id = data.get("vendor_id")
    risk_band = data.get("risk_band")
    if not vendor_id or risk_band not in (b.value for b in RiskBand):
        return
    db = SessionLocal()
    try:
        vendor = db.get(Vendor, vendor_id)
        if vendor:
            vendor.risk_band = RiskBand(risk_band)
            db.commit()
            logger.info("Updated vendor %s risk_band -> %s", vendor_id, risk_band)
    finally:
        db.close()


def _consume_loop():
    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="vendor-intelligence",
    )
    for message in consumer:
        try:
            envelope = message.value
            if envelope.get("event") == "risk.assessed":
                _handle_risk_assessed(envelope.get("data", {}))
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread() -> None:
    thread = threading.Thread(target=_consume_loop, daemon=True, name="vendor-risk-consumer")
    thread.start()
