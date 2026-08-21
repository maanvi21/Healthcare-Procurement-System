"""Records vendor behaviour from platform events, for `app/analytics.py` to measure.

Writes are idempotent on (source, source_id): Kafka redelivery must not inflate a
vendor's history, because history is exactly what the risk score is computed from — a
double-counted invoice would move a vendor's spend risk on its own.
"""
import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ObservationSource, VendorObservation

logger = logging.getLogger("risk_intelligence.observations")


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("₹", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def record(
    db: Session,
    vendor_id: str,
    source: ObservationSource,
    source_id: str,
    *,
    doc_type: str | None = None,
    amount=None,
    reference_number: str | None = None,
    fraud_flag: bool = False,
    fraud_score: float = 0.0,
    is_duplicate: bool = False,
    occurred_at: datetime | None = None,
) -> VendorObservation | None:
    """Returns the new observation, or None if this event was already recorded."""
    observation = VendorObservation(
        vendor_id=vendor_id,
        source=source,
        source_id=str(source_id),
        occurred_at=occurred_at or datetime.utcnow(),
        doc_type=doc_type,
        amount=_to_float(amount),
        reference_number=(reference_number or None),
        fraud_flag=bool(fraud_flag),
        fraud_score=float(fraud_score or 0.0),
        is_duplicate=bool(is_duplicate),
    )
    db.add(observation)
    try:
        db.commit()
    except IntegrityError:
        # unique (source, source_id) — this event was already recorded
        db.rollback()
        logger.debug("Observation %s/%s already recorded", source.value, source_id)
        return None
    db.refresh(observation)
    return observation


def record_document(db: Session, data: dict) -> VendorObservation | None:
    """From a `documents.processed` / `documents.reviewed` event."""
    vendor_id = data.get("vendor_id")
    document_id = data.get("document_id")
    if not vendor_id or not document_id:
        return None

    fields = data.get("fields") or {}
    return record(
        db, vendor_id, ObservationSource.document, document_id,
        doc_type=data.get("doc_type"),
        amount=fields.get("total_amount"),
        reference_number=fields.get("invoice_number") or fields.get("po_number"),
        fraud_flag=bool(data.get("fraud_flag")),
        fraud_score=float(data.get("fraud_score") or 0.0),
        is_duplicate=bool(data.get("is_duplicate")),
    )


def record_procurement_request(db: Session, data: dict) -> VendorObservation | None:
    """From a `procurement.request.created` event."""
    vendor_id = data.get("vendor_id")
    request_id = data.get("request_id")
    if not vendor_id or not request_id:
        return None
    return record(
        db, vendor_id, ObservationSource.procurement_request, request_id,
        amount=data.get("total_value"),
    )
