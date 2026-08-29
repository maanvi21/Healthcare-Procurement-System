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
import json
import logging
import threading
import uuid

from kafka import KafkaConsumer

from app.config import settings
from app.db import SessionLocal
from app.processing import process_document

logger = logging.getLogger("document_intelligence.kafka_consumer")

TOPICS = ["documents.ingested"]
GROUP_ID = "document-intelligence-ingest"


def _handle(envelope: dict) -> None:
    data = envelope.get("data") or {}
    raw_id = data.get("document_id")
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
                document_id, document.status.value, document.doc_type.value,
                document.overall_confidence,
            )
    finally:
        db.close()


def _consume_loop() -> None:
    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        group_id=GROUP_ID,
        # One document at a time per worker. OCR is the memory-hungry step, so fetching a
        # batch would put several documents' worth of pipeline in memory at once — the
        # very thing that was killing the container.
        max_poll_records=1,
        # OCR plus two LLM calls can take a while; without this the broker decides the
        # worker is dead mid-document and rebalances the partition away from it.
        max_poll_interval_ms=600000,
    )
    for message in consumer:
        try:
            _handle(message.value or {})
        except Exception:
            logger.exception("Failed processing message at offset %s", message.offset)
        finally:
            # Commit either way: a document that fails deterministically (corrupt file,
            # unreadable scan) would otherwise be retried forever and block the partition
            # behind it. The failure is logged and the document stays in `received`, where
            # the review queue can surface it.
            consumer.commit()


def start_consumer_thread() -> None:
    thread = threading.Thread(target=_consume_loop, daemon=True, name="document-ingest-consumer")
    thread.start()
