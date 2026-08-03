import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import extraction, minio_client, ocr
from app.classification import classify
from app.config import settings
from app.db import get_db
from app.kafka_producer import publish_event
from app.models import Document, DocumentSource, DocumentStatus, DuplicateFlag, ExtractedField
from app.schemas import DocumentOut, DocumentSummary, FieldCorrection

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=DocumentOut)
def ingest_document(
    file: UploadFile = File(...),
    source: DocumentSource = Query(default=DocumentSource.upload),
    db: Session = Depends(get_db),
):
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(400, "Empty file")

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    object_key = f"{uuid.uuid4()}/{file.filename}"
    minio_client.upload_bytes(object_key, file_bytes, file.content_type or "application/octet-stream")

    document = Document(
        source=source,
        original_filename=file.filename,
        minio_object_key=object_key,
        content_hash=content_hash,
        status=DocumentStatus.processing,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    publish_event("documents.ingested", str(document.id), {
        "document_id": str(document.id), "source": source.value,
    })

    # duplicate detection by content hash — same bytes uploaded twice
    duplicate = db.execute(
        select(Document).where(Document.content_hash == content_hash, Document.id != document.id)
    ).scalars().first()
    if duplicate:
        db.add(DuplicateFlag(
            document_id=document.id, duplicate_of_document_id=duplicate.id,
            reason="identical content hash",
        ))

    text, ocr_confidence = ocr.extract_text(file_bytes, file.content_type or "")
    doc_type, classification_confidence = classify(text)
    fields = extraction.extract_fields(text, ocr_confidence)

    document.doc_type = doc_type
    document.classification_confidence = classification_confidence
    document.processed_at = datetime.utcnow()

    any_low_confidence = classification_confidence < settings.review_confidence_threshold
    for field_name, (value, confidence) in fields.items():
        db.add(ExtractedField(
            document_id=document.id, field_name=field_name, field_value=value, confidence=confidence,
        ))
        if confidence < settings.review_confidence_threshold:
            any_low_confidence = True

    missing = extraction.missing_required_fields(doc_type.value, fields)
    document.status = DocumentStatus.needs_review if (any_low_confidence or missing or duplicate) else DocumentStatus.extracted

    db.commit()
    db.refresh(document)

    publish_event("documents.processed", str(document.id), {
        "document_id": str(document.id),
        "doc_type": doc_type.value,
        "vendor_id": str(document.vendor_id) if document.vendor_id else None,
        "status": document.status.value,
        "fields": {k: v[0] for k, v in fields.items()},
    })
    return document


@router.get("", response_model=list[DocumentSummary])
def list_documents(status: DocumentStatus | None = None, db: Session = Depends(get_db)):
    query = select(Document).order_by(Document.uploaded_at.desc())
    if status:
        query = query.where(Document.status == status)
    return db.execute(query).scalars().all()


@router.get("/review-queue", response_model=list[DocumentSummary])
def review_queue(db: Session = Depends(get_db)):
    query = select(Document).where(Document.status == DocumentStatus.needs_review).order_by(Document.uploaded_at)
    return db.execute(query).scalars().all()


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return document


@router.post("/{document_id}/fields/{field_id}/correct", response_model=DocumentOut)
def correct_field(document_id: uuid.UUID, field_id: uuid.UUID, payload: FieldCorrection, db: Session = Depends(get_db)):
    field = db.get(ExtractedField, field_id)
    if not field or field.document_id != document_id:
        raise HTTPException(404, "Field not found")
    field.field_value = payload.field_value
    field.confidence = 1.0
    field.is_manually_corrected = True
    db.commit()

    document = db.get(Document, document_id)
    still_low_confidence = any(f.confidence < settings.review_confidence_threshold for f in document.extracted_fields)
    if not still_low_confidence and document.status == DocumentStatus.needs_review:
        document.status = DocumentStatus.validated
        db.commit()
    db.refresh(document)
    return document
