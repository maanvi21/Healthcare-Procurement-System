"""Background Kafka consumer for vendor_intelligence.

Two subscriptions, both keeping the vendor master record current from events other
services emit:

- `risk.assessed` (risk_intelligence) — refreshes the vendor's risk_band.
- `documents.processed` / `documents.reviewed` (document_intelligence) — files the
  document against the vendor it was attributed to, so a vendor's compliance
  certificates, invoices and POs accumulate on their profile automatically.

Runs as a daemon thread started from main.py's startup event so the FastAPI app and the
consumer share the process but not the request loop."""
import json
import logging
import threading

from kafka import KafkaConsumer

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import RiskBand, Vendor, VendorDocument

logger = logging.getLogger("vendor_intelligence.kafka_consumer")

TOPICS = ["risk.assessed", "documents.processed", "documents.reviewed"]

# only these document types are worth filing against a vendor profile; a delivery note or
# an unclassified scan carries no lasting compliance meaning
_FILEABLE_DOC_TYPES = {
    "invoice", "purchase_order", "quotation", "compliance_certificate", "vendor_registration",
}


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


def _handle_document_event(data: dict) -> None:
    """File a processed document against the vendor it was attributed to.

    Skips documents with no resolved vendor (document_intelligence could not match the
    OCR'd name confidently — those sit in its review queue until a human attaches one),
    and is idempotent: Kafka redelivery or a document being reviewed after it was
    processed must not create a duplicate link row.
    """
    vendor_id = data.get("vendor_id")
    document_id = data.get("document_id")
    doc_type = data.get("doc_type")

    if not vendor_id or not document_id:
        return
    if doc_type not in _FILEABLE_DOC_TYPES:
        return

    db = SessionLocal()
    try:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            logger.warning("Document %s references unknown vendor %s", document_id, vendor_id)
            return

        existing = db.execute(
            select(VendorDocument).where(
                VendorDocument.vendor_id == vendor_id,
                VendorDocument.document_id == document_id,
            )
        ).scalars().first()
        if existing:
            # a reviewed document may arrive twice; keep the purpose current and move on
            if existing.doc_purpose != doc_type:
                existing.doc_purpose = doc_type
                db.commit()
            return

        db.add(VendorDocument(vendor_id=vendor_id, document_id=document_id, doc_purpose=doc_type))
        db.commit()
        logger.info("Filed %s document %s against vendor %s", doc_type, document_id, vendor_id)
    except Exception:
        db.rollback()
        raise
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
            event = envelope.get("event")
            data = envelope.get("data", {})
            if event == "risk.assessed":
                _handle_risk_assessed(data)
            elif event in ("documents.processed", "documents.reviewed"):
                _handle_document_event(data)
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread() -> None:
    thread = threading.Thread(target=_consume_loop, daemon=True, name="vendor-event-consumer")
    thread.start()
