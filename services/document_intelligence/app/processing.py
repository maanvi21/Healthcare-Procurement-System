"""The OCR → classify → extract → fraud-screen pipeline, and the event it publishes.

Lifted out of the ingest HTTP handler so it can run in a Kafka consumer instead. It used
to execute inline in the request, which had two consequences:

* An upload blocked for as long as OCR and the LLM calls took — around 20 seconds — so a
  browser upload felt broken and a caller uploading a batch waited serially.
* Concurrency was unbounded. Six simultaneous uploads meant six PaddleOCR pipelines
  resident at once, which exhausted memory and got the container OOM-killed. Nothing
  limited how many documents were in flight, because the limit was however many HTTP
  requests happened to arrive together.

Running it from a consumer fixes both. The upload returns as soon as the bytes are
durable, and the number of documents being processed at once is the number of consumer
processes — a number the deployment controls, not the callers.
"""
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import extraction, fraud, minio_client, ocr, vendor_client
from app.classification import classify
from app.config import settings
from app.kafka_producer import publish_event
from app.models import Document, DocumentStatus, DuplicateFlag, ExtractedField

logger = logging.getLogger("document_intelligence.processing")

_RAW_TEXT_LIMIT = 20000

# Statuses that mean the pipeline has already run for this document. Kafka redelivers on
# rebalance or restart, and re-running would duplicate ExtractedField rows and re-publish
# documents.processed, which would raise a second procurement request downstream.
_ALREADY_PROCESSED = {
    DocumentStatus.extracted,
    DocumentStatus.needs_review,
    DocumentStatus.validated,
    DocumentStatus.rejected,
    DocumentStatus.failed,
}


def _content_type_for(document: Document) -> str:
    """OCR only needs to know PDF from image, and the stored filename is enough."""
    return "application/pdf" if document.original_filename.lower().endswith(".pdf") else "image/png"


def process_document(db: Session, document_id: uuid.UUID) -> Document | None:
    """Run the full pipeline for one already-stored document and publish the result.

    Returns None when the document is missing or has already been processed, so a
    redelivered message is a no-op rather than a duplicate.
    """
    document = db.get(Document, document_id)
    if document is None:
        logger.warning("Document %s no longer exists — dropping", document_id)
        return None
    if document.status in _ALREADY_PROCESSED:
        logger.info("Document %s already processed (%s) — skipping", document_id, document.status.value)
        return None

    document.status = DocumentStatus.processing
    document.processing_error = None
    db.commit()

    file_bytes = minio_client.download_bytes(document.minio_object_key)

    # duplicate detection by content hash — same bytes uploaded twice
    duplicate = db.execute(
        select(Document).where(
            Document.content_hash == document.content_hash, Document.id != document.id
        )
    ).scalars().first()
    if duplicate:
        db.add(DuplicateFlag(
            document_id=document.id, duplicate_of_document_id=duplicate.id,
            reason="identical content hash",
        ))

    text, ocr_confidence = ocr.extract_text(file_bytes, _content_type_for(document))
    doc_type, classification_confidence = classify(text)
    fields, engine = extraction.extract_fields(
        text, ocr_confidence, doc_type.value, classification_confidence
    )

    # fraud screen runs on the extracted view of the document, not the raw bytes
    fraud_result = fraud.screen(text, {name: value for name, (value, _) in fields.items()})

    overall_confidence = round((ocr_confidence + classification_confidence) / 2, 2)

    # attach the document to a known vendor so downstream services can key off an id.
    # Fails soft — an unresolved vendor leaves vendor_id null and routes to manual review.
    vendor_name = fields.get("vendor_name", (None,))[0]
    resolved_vendor_id = vendor_client.resolve_vendor_id(vendor_name)
    if resolved_vendor_id:
        try:
            document.vendor_id = uuid.UUID(resolved_vendor_id)
        except (ValueError, AttributeError):
            logger.warning("Vendor service returned an unusable id %r", resolved_vendor_id)

    document.doc_type = doc_type
    document.classification_confidence = classification_confidence
    document.ocr_confidence = round(ocr_confidence, 2)
    document.overall_confidence = overall_confidence
    document.extraction_engine = engine
    document.fraud_flag = bool(fraud_result["fraud_detected"])
    document.fraud_score = fraud_result["fraud_score"]
    document.raw_text = text[:_RAW_TEXT_LIMIT]
    document.processed_at = datetime.utcnow()

    any_low_confidence = overall_confidence < settings.review_confidence_threshold
    for field_name, (value, confidence) in fields.items():
        db.add(ExtractedField(
            document_id=document.id, field_name=field_name, field_value=value, confidence=confidence,
        ))
        if confidence < settings.review_confidence_threshold:
            any_low_confidence = True

    missing = extraction.missing_required_fields(doc_type.value, fields)
    document.extraction_notes = json.dumps({
        "ocr_confidence": round(ocr_confidence, 2),
        "classification_confidence": classification_confidence,
        "overall_confidence": overall_confidence,
        "extraction_engine": engine,
        "fraud_score": fraud_result["fraud_score"],
        "fraud_flags": fraud_result["flags"],
        "fraud_engine": fraud_result["engine"],
        "fraud_recommendation": fraud_result["recommendation"],
        "missing_required_fields": missing,
        "vendor_name_extracted": vendor_name,
        "vendor_resolved": document.vendor_id is not None,
    })

    needs_review = (
        any_low_confidence
        or bool(missing)
        or duplicate is not None
        or fraud_result["fraud_score"] >= settings.fraud_review_threshold
        or document.fraud_flag
        # a document nobody can attribute to a vendor cannot drive an approval
        or document.vendor_id is None
    )
    document.status = DocumentStatus.needs_review if needs_review else DocumentStatus.extracted

    db.commit()
    db.refresh(document)

    if document.watcher_input_path:
        from app.file_watcher import finalize_watched_file
        document.watcher_input_path = finalize_watched_file(document, "processed")
        db.commit()

    publish_event("documents.processed", str(document.id), {
        "document_id": str(document.id),
        "doc_type": doc_type.value,
        "vendor_id": str(document.vendor_id) if document.vendor_id else None,
        "status": document.status.value,
        "confidence": overall_confidence,
        "fraud_flag": document.fraud_flag,
        "fraud_score": document.fraud_score,
        "is_duplicate": duplicate is not None,
        "fields": {k: v[0] for k, v in fields.items()},
    })
    return document
