"""Background consumer: reacts to procurement lifecycle events published by
approval_workflow.

- `procurement.request.created` (fired the moment a request is submitted, in parallel
  with approval routing) triggers an immediate stock check + reservation attempt per
  line item, keyed by SKU.
- `approval.rejected` releases any reservations held against a request that didn't get
  approved, so the stock becomes available again without waiting for the hold to expire.
"""
import json
import logging
import threading

from app.config import settings
from app.db import SessionLocal
from app.models import StockItem
from app.reservation import release_reservations_for_request, reserve_stock

logger = logging.getLogger("inventory_intelligence.kafka_consumer")

TOPICS = ["procurement.request.created", "approval.rejected"]


def _handle_request_created(data: dict) -> None:
    request_id = data.get("request_id")
    items = data.get("items") or []
    if not request_id or not items:
        return
    db = SessionLocal()
    try:
        for item in items:
            sku = item.get("sku")
            quantity = int(item.get("quantity", 0))
            if not sku or quantity <= 0:
                continue
            stock_item = db.query(StockItem).filter(StockItem.sku == sku).first()
            if not stock_item:
                logger.warning("No stock item for SKU %s on request %s", sku, request_id)
                continue
            reserve_stock(db, stock_item.id, quantity, request_id)
    finally:
        db.close()


def _handle_request_rejected(data: dict) -> None:
    request_id = data.get("request_id")
    if not request_id:
        return
    db = SessionLocal()
    try:
        released = release_reservations_for_request(db, request_id)
        logger.info("Released %d reservation(s) for rejected request %s", released, request_id)
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
        group_id="inventory-intelligence",
    )
    for message in consumer:
        try:
            envelope = message.value
            event = envelope.get("event")
            data = envelope.get("data", {})
            if event == "procurement.request.created":
                _handle_request_created(data)
            elif event == "approval.rejected":
                _handle_request_rejected(data)
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread() -> None:
    thread = threading.Thread(target=_consume_loop, daemon=True, name="inventory-event-consumer")
    thread.start()
