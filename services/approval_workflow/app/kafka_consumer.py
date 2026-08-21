"""Background Kafka consumer: turns a processed procurement document into a request.

This is step 1→2 of the platform flow — an invoice or PO that document_intelligence has
read cleanly becomes a `ProcurementRequest`, which is then routed through OPA, Temporal
and the approver chain exactly as a hand-raised request would be.

The gating is deliberately strict, because this path creates work for human approvers
without a human having asked for it. A document only raises a request when it is:

  * an `invoice` or `purchase_order` (a quotation or compliance cert is not a commitment),
  * `extracted` (read cleanly) or `validated` (a human signed off in the review queue) —
    never `needs_review`,
  * attributed to a known vendor, and
  * carrying a positive, parseable total.

Anything else is logged and dropped. A document that fails the gate is not lost: it sits
in document_intelligence's review queue, and the `documents.reviewed` event re-runs this
same check once a human has fixed it.

Idempotency is enforced by a unique `source_document_id` on the request, so Kafka
redelivery — or a document being both processed and later reviewed — cannot raise the
same request twice.

Threading note: request creation is async (Temporal), but Kafka consumption is a blocking
loop in a plain thread. Rather than `asyncio.run()` — which would build a fresh event loop
per message and hand the module-level Temporal client to a loop it was not created on —
the coroutine is submitted back to the app's main loop with
`run_coroutine_threadsafe`. One loop owns the Temporal connection, always.
"""
import asyncio
import json
import logging
import threading

from kafka import KafkaConsumer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import SessionLocal
from app.models import ProcurementRequest
from app.schemas import ProcurementRequestCreate
from app.service import create_procurement_request

logger = logging.getLogger("approval_workflow.kafka_consumer")

# the app's main event loop, captured at startup — see the threading note above
_loop: asyncio.AbstractEventLoop | None = None

# a request creation waits on OPA + Temporal + Postgres; generous but bounded
_CREATE_TIMEOUT_SECONDS = 60

TOPICS = ["documents.processed", "documents.reviewed"]

# document types that represent an actual procurement commitment
_ACTIONABLE_DOC_TYPES = {"invoice", "purchase_order"}
# statuses that mean the extraction is trustworthy enough to act on
_ACTIONABLE_STATUSES = {"extracted", "validated"}


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("₹", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_items(raw) -> list[dict]:
    """Normalise extracted line items into the shape approvals/inventory expect.

    `sku` is what inventory_intelligence reserves stock against. Documents rarely carry a
    hospital-internal SKU, so it is passed through when present and left blank otherwise —
    the request is still routable and approvable, it just won't auto-reserve stock.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        quantity = _to_float(entry.get("quantity")) or 0
        items.append({
            "sku": str(entry.get("sku") or "").strip(),
            "description": str(entry.get("name") or entry.get("description") or "").strip(),
            "quantity": int(quantity) if quantity > 0 else 0,
            "unit_price": _to_float(entry.get("unit_price")),
        })
    return items


def _already_raised(document_id: str) -> bool:
    db = SessionLocal()
    try:
        return db.execute(
            select(ProcurementRequest.id).where(ProcurementRequest.source_document_id == document_id)
        ).first() is not None
    finally:
        db.close()


def _handle_document(data: dict) -> None:
    document_id = data.get("document_id")
    doc_type = data.get("doc_type")
    status = data.get("status")
    vendor_id = data.get("vendor_id")
    fields = data.get("fields") or {}

    if not document_id:
        return
    if doc_type not in _ACTIONABLE_DOC_TYPES:
        logger.debug("Document %s is a %s — not a procurement commitment", document_id, doc_type)
        return
    if status not in _ACTIONABLE_STATUSES:
        logger.info("Document %s is %s — waiting for review before raising a request", document_id, status)
        return
    if not vendor_id:
        logger.info("Document %s has no resolved vendor — cannot raise a request", document_id)
        return

    total_value = _to_float(fields.get("total_amount"))
    if total_value is None or total_value <= 0:
        logger.info("Document %s has no usable total_amount — cannot route for approval", document_id)
        return

    if _already_raised(document_id):
        logger.info("Document %s already raised a procurement request — skipping", document_id)
        return

    payload = ProcurementRequestCreate(
        requested_by=f"document_intelligence:{document_id}",
        department=settings.document_default_department,
        category=settings.document_default_category,
        vendor_id=vendor_id,
        vendor_risk_band=None,  # risk_intelligence updates the vendor's band independently
        items=_parse_items(fields.get("line_items")),
        total_value=total_value,
    )

    if _loop is None:
        logger.error("Consumer has no event loop — dropping document %s", document_id)
        return

    future = asyncio.run_coroutine_threadsafe(
        create_procurement_request(payload, source_document_id=document_id), _loop
    )
    try:
        request_id = future.result(timeout=_CREATE_TIMEOUT_SECONDS)
    except IntegrityError:
        # lost a race with a concurrent delivery of the same document — the other one won
        logger.info("Document %s raised concurrently elsewhere — skipping", document_id)
        return
    except TimeoutError:
        logger.error("Timed out raising a request for document %s", document_id)
        return
    logger.info("Document %s raised procurement request %s (%.2f)", document_id, request_id, total_value)


def _consume_loop():
    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="approval-workflow",
    )
    for message in consumer:
        try:
            envelope = message.value
            if envelope.get("event") in ("documents.processed", "documents.reviewed"):
                _handle_document(envelope.get("data", {}))
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread(loop: asyncio.AbstractEventLoop) -> None:
    """Call from an async startup handler, passing `asyncio.get_running_loop()`."""
    global _loop
    _loop = loop
    thread = threading.Thread(target=_consume_loop, daemon=True, name="approval-document-consumer")
    thread.start()
