"""Background consumer: keeps every vendor's risk assessment current.

Two kinds of event, handled differently:

**Vendor events** (`vendor.onboarded`, `vendor.updated`) — master data changed, so
re-assess immediately.

**Behaviour events** (`documents.processed`, `documents.reviewed`,
`procurement.request.created`) — these carry the spend and fraud signals that the risk
model measures. Each is recorded as an observation first, then the vendor is re-assessed
so the new evidence is reflected in their band.

Re-assessing on every single event would be wasteful (an assessment loads the MLflow
model and hits vendor_intelligence), so behaviour-driven re-assessment is debounced per
vendor: a vendor is re-scored at most once per `risk_reassess_debounce_seconds`. The
observation itself is always recorded immediately, so nothing is lost — only the scoring
is coalesced.

The debounce is leading *and* trailing. A leading-only debounce scores the first event of
a burst and drops the rest, which would leave a vendor who submits twenty invoices in a
minute assessed on the strength of one — and that burst is precisely what anomaly
detection exists to catch. Events arriving inside the window instead mark the vendor
dirty, and a flusher thread re-scores dirty vendors once the window closes, so the stored
assessment always reflects the vendor's final state rather than the moment the burst
began.
"""
import json
import logging
import threading
import time

from app.config import settings
from app.db import SessionLocal
from app.models import ObservationSource
from app.observations import record_document, record_procurement_request
from app.service import assess_vendor

logger = logging.getLogger("risk_intelligence.kafka_consumer")

TOPICS = [
    "vendor.onboarded", "vendor.updated",
    "documents.processed", "documents.reviewed",
    "procurement.request.created",
]

_VENDOR_EVENTS = {"vendor.onboarded", "vendor.updated"}
_DOCUMENT_EVENTS = {"documents.processed", "documents.reviewed"}

# vendor_id -> last assessment timestamp, for debouncing
_last_assessed: dict[str, float] = {}
# vendors that saw activity while debounced and still need a trailing re-score
_dirty: set[str] = set()
_lock = threading.Lock()


def _should_reassess(vendor_id: str, force: bool = False) -> bool:
    now = time.monotonic()
    with _lock:
        last = _last_assessed.get(vendor_id, 0.0)
        if force or (now - last) >= settings.risk_reassess_debounce_seconds:
            _last_assessed[vendor_id] = now
            return True
    return False


def _reassess(vendor_id: str, force: bool = False) -> None:
    if not _should_reassess(vendor_id, force=force):
        # debounced — remember to re-score once the window closes
        with _lock:
            _dirty.add(vendor_id)
        logger.debug("Deferred re-assessment of %s (debounced)", vendor_id)
        return
    db = SessionLocal()
    try:
        assess_vendor(db, vendor_id)
        logger.info("Assessed risk for vendor %s", vendor_id)
    except Exception:
        logger.exception("Risk assessment failed for vendor %s", vendor_id)
    finally:
        db.close()


def _handle_vendor_event(data: dict) -> None:
    vendor_id = data.get("vendor_id")
    if vendor_id:
        # master data changed — always re-score, never debounce
        _reassess(vendor_id, force=True)


def _handle_behaviour_event(event: str, data: dict) -> None:
    vendor_id = data.get("vendor_id")
    if not vendor_id:
        # an unattributed document carries no vendor signal — document_intelligence will
        # re-publish once a reviewer resolves the vendor
        return

    db = SessionLocal()
    try:
        if event in _DOCUMENT_EVENTS:
            observation = record_document(db, data)
        else:
            observation = record_procurement_request(db, data)
    except Exception:
        logger.exception("Failed to record observation from %s", event)
        return
    finally:
        db.close()

    if observation is None:
        return  # already recorded; nothing new to score
    _reassess(vendor_id)


def _flush_loop():
    """Re-scores vendors that saw activity while their debounce window was open."""
    interval = max(1.0, settings.risk_reassess_debounce_seconds)
    while True:
        time.sleep(interval)
        with _lock:
            pending = list(_dirty)
            _dirty.clear()
        for vendor_id in pending:
            try:
                _reassess(vendor_id, force=True)
            except Exception:
                logger.exception("Trailing re-assessment failed for vendor %s", vendor_id)


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
            event = envelope.get("event")
            data = envelope.get("data", {})
            if event in _VENDOR_EVENTS:
                _handle_vendor_event(data)
            elif event in _DOCUMENT_EVENTS or event == "procurement.request.created":
                _handle_behaviour_event(event, data)
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread() -> None:
    threading.Thread(target=_consume_loop, daemon=True, name="risk-event-consumer").start()
    threading.Thread(target=_flush_loop, daemon=True, name="risk-reassess-flusher").start()
