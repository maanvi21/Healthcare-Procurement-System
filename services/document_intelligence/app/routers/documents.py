import hashlib
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import minio_client, vendor_client
from app.auth import require_roles
from app.config import settings
from app.db import get_db
from app.kafka_producer import publish_event
from app.models import Document, DocumentSource, DocumentStatus, DuplicateFlag, ExtractedField
from app.schemas import DocumentOut, DocumentReview, DocumentSummary, FieldCorrection

logger = logging.getLogger(__name__)

# OCR text stored on the row for audit; the full document always stays in MinIO
_RAW_TEXT_LIMIT = 5000

_SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/bmp",
}
_SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=DocumentOut, status_code=202)
def ingest_document(
    file: UploadFile = File(...),
    source: DocumentSource = Query(default=DocumentSource.upload),
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["department_manager", "procurement_director"])),
):
    """Accept a document, make it durable, and hand the work to the ingest consumer.

    Returns 202 with the document in `received`: the bytes are stored and the event is
    published, but OCR/extraction have not run yet. Poll `GET /documents/{id}` — the
    status becomes `extracted` or `needs_review` once a worker finishes.

    This handler used to run the whole pipeline inline, which meant a caller waited ~20s
    per upload and concurrency was whatever the callers happened to send. A batch of six
    put six OCR pipelines in memory at once and OOM-killed the container. The work now
    runs in app/kafka_consumer.py, where the deployment decides how many run at a time.
    """
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    extension = Path(file.filename or "").suffix.lower()
    # Browsers and curl disagree about content types for the same file, so accept a match
    # on either signal rather than rejecting a valid PDF sent as octet-stream.
    if content_type not in _SUPPORTED_CONTENT_TYPES and extension not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            415,
            f"Unsupported file type '{file.content_type or extension or 'unknown'}'. "
            "Upload a PDF or an image (PNG, JPEG, TIFF, BMP).",
        )

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
        status=DocumentStatus.received,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Published last, once the row and the bytes are both durable — a consumer may pick
    # this up on another replica microseconds later and must find the document there.
    publish_event("documents.ingested", str(document.id), {
        "document_id": str(document.id), "source": source.value,
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


@router.put("/{document_id}/review", response_model=DocumentOut)
def review_document(
    document_id: uuid.UUID,
    payload: DocumentReview,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["department_manager", "compliance_officer", "procurement_director"])),
):
    """Document-level manual review: accept a corrected doc_type and/or a batch of field
    corrections in one call, then mark the document validated.

    Complements `/fields/{field_id}/correct`, which corrects a single field in place —
    this is what the reviewer's "save and approve" button calls.
    """
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")

    if payload.doc_type is not None:
        document.doc_type = payload.doc_type

    if payload.fields:
        existing = {f.field_name: f for f in document.extracted_fields}
        for field_name, field_value in payload.fields.items():
            field = existing.get(field_name)
            if field:
                field.field_value = field_value
            else:
                field = ExtractedField(
                    document_id=document.id, field_name=field_name, field_value=field_value,
                )
                db.add(field)
            field.confidence = 1.0
            field.is_manually_corrected = True

    if payload.fraud_flag is not None:
        document.fraud_flag = payload.fraud_flag

    # a reviewer correcting the vendor name is the main way an unresolved document gets
    # attached to a vendor — re-run resolution against the corrected value
    if payload.vendor_id is not None:
        document.vendor_id = payload.vendor_id
    elif "vendor_name" in payload.fields and document.vendor_id is None:
        resolved = vendor_client.resolve_vendor_id(payload.fields["vendor_name"])
        if resolved:
            try:
                document.vendor_id = uuid.UUID(resolved)
            except (ValueError, AttributeError):
                logger.warning("Vendor service returned an unusable id %r", resolved)

    document.status = payload.status or DocumentStatus.validated
    db.commit()
    db.refresh(document)

    publish_event("documents.reviewed", str(document.id), {
        "document_id": str(document.id),
        "doc_type": document.doc_type.value,
        "status": document.status.value,
        "vendor_id": str(document.vendor_id) if document.vendor_id else None,
        "fraud_flag": document.fraud_flag,
        "fields": {f.field_name: f.field_value for f in document.extracted_fields},
    })
    return document


@router.delete("/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["procurement_director"])),
):
    """Delete a document row and its extracted fields/duplicate flags.

    The object in MinIO is left in place deliberately — procurement documents are an
    audit trail, so this removes the record from the working queue without destroying
    the underlying evidence.
    """
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")

    db.execute(
        delete(DuplicateFlag).where(
            (DuplicateFlag.document_id == document_id)
            | (DuplicateFlag.duplicate_of_document_id == document_id)
        )
    )
    db.delete(document)
    db.commit()
    return {"message": "Document deleted successfully", "id": str(document_id)}
