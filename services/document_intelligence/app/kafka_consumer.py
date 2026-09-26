"""Background consumer that processes ingested documents.

This is the worker half of ingestion. `POST /documents/ingest` now only makes the bytes
durable (MinIO + a `received` row) and publishes `documents.ingested`; the OCR, LLM
classification, field extraction and fraud screen all happen here, off the request path.

Why it matters beyond response times: the number of documents being processed at once is
now the number of consumer processes, not the number of HTTP requests that happened to
arrive together. Scaling is `--scale document_intelligence=N`, and Kafka hands each
replica a share of the partitions on `documents.ingested`. Before this, six simultaneous
uploads meant six concurrent PaddleOCR pipelines in one container and an OOM kill.

`enable_auto_commit=False` is deliberate. With auto-commit, Kafka records the offset on a
timer regardless of what happened to the message, so a document whose processing crashed
mid-way would be marked done and silently never retried. Committing only after
`process_document` returns means a crash leaves the offset where it was and the document
is picked up again — at-least-once delivery, which `process_document` is written to
tolerate because it skips documents that already carry a processed status.
"""
from collections import deque
from datetime import datetime, timezone
import json
import logging
import threading
import uuid

try:
    from kafka import KafkaConsumer, KafkaAdminClient
except Exception as _kafka_err:
    KafkaConsumer = None
    KafkaAdminClient = None

from app.config import settings
from app.db import SessionLocal
from app.processing import process_document
from app.models import Document, DocumentStatus

logger = logging.getLogger("document_intelligence.kafka_consumer")

TOPICS = ["documents.ingested"]
GROUP_ID = "document-intelligence-ingest"

# Telemetry store for live status monitoring
_telemetry_lock = threading.Lock()
_consumer_thread: threading.Thread | None = None

_telemetry = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "total_processed": 0,
    "total_failed": 0,
    "recent_events": deque(maxlen=25),
    "source_counts": {"upload": 0, "email": 0, "api": 0, "shared_folder": 0},
    "last_event_at": None,
}


def record_kafka_event(
    document_id: str,
    original_filename: str,
    source: str,
    status: str,
    error: str | None = None,
) -> None:
    """Record an ingested or processed Kafka event for live telemetry."""
    now = datetime.now(timezone.utc).isoformat()
    s = source if source in _telemetry["source_counts"] else "upload"

    with _telemetry_lock:
        if error:
            _telemetry["total_failed"] += 1
        else:
            _telemetry["total_processed"] += 1
        _telemetry["last_event_at"] = now
        _telemetry["source_counts"][s] = _telemetry["source_counts"].get(s, 0) + 1

        _telemetry["recent_events"].appendleft(
            {
                "id": str(uuid.uuid4())[:8],
                "document_id": str(document_id),
                "original_filename": original_filename or "document.pdf",
                "source": s,
                "status": status,
                "timestamp": now,
                "error": error,
            }
        )


def check_kafka_connectivity() -> bool:
    """Check if the Kafka broker is reachable."""
    if not KafkaAdminClient:
        return False
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
            request_timeout_ms=1000,
        )
        admin.close()
        return True
    except Exception:
        return False


def get_kafka_telemetry(db=None) -> dict:
    """Retrieve full Kafka telemetry status payload."""
    is_connected = check_kafka_connectivity()
    is_worker_alive = bool(_consumer_thread and _consumer_thread.is_alive())

    queue_lag = 0
    if db:
        try:
            queue_lag = (
                db.query(Document)
                .filter(Document.status == DocumentStatus.received)
                .count()
            )
        except Exception:
            queue_lag = 0

    with _telemetry_lock:
        return {
            "status": "active" if (is_connected or is_worker_alive) else "idle",
            "broker": settings.kafka_bootstrap_servers,
            "consumer_group": GROUP_ID,
            "topics": TOPICS,
            "is_connected": is_connected,
            "worker_thread_alive": is_worker_alive,
            "metrics": {
                "total_processed": _telemetry["total_processed"],
                "total_failed": _telemetry["total_failed"],
                "queue_lag": queue_lag,
                "source_breakdown": dict(_telemetry["source_counts"]),
                "last_event_at": _telemetry["last_event_at"],
            },
            "recent_events": list(_telemetry["recent_events"]),
        }


def _handle(envelope: dict) -> None:
    data = envelope.get("data") or {}
    raw_id = data.get("document_id")
    source = data.get("source") or "upload"
    if not raw_id:
        return
    try:
        document_id = uuid.UUID(str(raw_id))
    except ValueError:
        logger.warning("Ignoring documents.ingested with unusable id %r", raw_id)
        return

    db = SessionLocal()
    try:
        document = process_document(db, document_id)
        if document is not None:
            logger.info(
                "Processed document %s -> %s (%s, confidence %.2f)",
                document_id,
                document.status.value,
                document.doc_type.value,
                document.overall_confidence,
            )
            record_kafka_event(
                document_id=str(document.id),
                original_filename=document.original_filename,
                source=source,
                status=document.status.value,
            )
    except Exception as e:
        record_kafka_event(
            document_id=str(document_id),
            original_filename="document",
            source=source,
            status="failed",
            error=str(e),
        )
        raise
    finally:
        db.close()


def _consume_loop() -> None:
    try:
        consumer = KafkaConsumer(
            *TOPICS,
            bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            group_id=GROUP_ID,
            max_poll_records=1,
            max_poll_interval_ms=600000,
        )
        for message in consumer:
            try:
                _handle(message.value or {})
            except Exception:
                logger.exception("Failed processing message at offset %s", message.offset)
            finally:
                consumer.commit()
    except Exception as e:
        logger.warning("Kafka consumer loop stopped or unavailable: %s", e)


def start_consumer_thread() -> None:
    global _consumer_thread
    _consumer_thread = threading.Thread(
        target=_consume_loop, daemon=True, name="document-ingest-consumer"
    )
    _consumer_thread.start()

