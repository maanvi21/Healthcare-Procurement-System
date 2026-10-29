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
from app.kafka_consumer import get_kafka_telemetry, record_kafka_event
from app.kafka_producer import publish_event
from app.file_watcher import get_watcher_telemetry
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
    _role: str = Depends(require_roles(["department_manager", "compliance_officer", "procurement_director"])),
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


@router.get("/kafka-status")
def get_kafka_status(db: Session = Depends(get_db)):
    """Retrieve live Kafka event stream telemetry & consumer status."""
    return get_kafka_telemetry(db)


@router.post("/kafka/simulate-input")
def simulate_kafka_input(
    source: DocumentSource = Query(default=DocumentSource.email),
    filename: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Simulate a live Kafka document ingestion event from external sources (e.g. Email, API webhook, Shared folder)."""
    # Unpack FastAPI Query objects if invoked directly in python
    if hasattr(source, "default"):
        source = source.default
    if isinstance(source, str):
        try:
            source = DocumentSource(source)
        except ValueError:
            source = DocumentSource.email

    actual_source_val = source.value if hasattr(source, "value") else str(source)

    if not isinstance(filename, str):
        filename = None

    sample_files = {
        DocumentSource.email.value: ("email_supplier_invoice_1092.pdf", b"%PDF-1.4 Mock Supplier Invoice Content from Email Stream"),
        DocumentSource.api.value: ("api_po_payload_883.pdf", b"%PDF-1.4 Mock PO Payload from ERP API Webhook Stream"),
        DocumentSource.shared_folder.value: ("shared_delivery_note_404.pdf", b"%PDF-1.4 Mock Delivery Note from Network Folder Stream"),
        DocumentSource.upload.value: ("portal_upload_spec.pdf", b"%PDF-1.4 Mock Upload Document"),
    }
    default_name, default_bytes = sample_files.get(actual_source_val, sample_files[DocumentSource.email.value])
    actual_filename = filename or f"{actual_source_val}_{int(datetime.now().timestamp())}.pdf"

    content_hash = hashlib.sha256(default_bytes).hexdigest()
    object_key = f"simulated/{uuid.uuid4()}/{actual_filename}"
    try:
        minio_client.upload_bytes(object_key, default_bytes, "application/pdf")
    except Exception:
        pass  # non-blocking if minio is offline

    document = Document(
        source=source,
        original_filename=actual_filename,
        minio_object_key=object_key,
        content_hash=content_hash,
        status=DocumentStatus.received,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Publish event to Kafka
    event_published = False
    try:
        publish_event("documents.ingested", str(document.id), {
            "document_id": str(document.id),
            "source": source.value if hasattr(source, "value") else str(source),
            "filename": actual_filename,
        })
        event_published = True
    except Exception as e:
        logger.warning("Could not publish event to Kafka broker: %s", e)

    # Record telemetry
    record_kafka_event(
        document_id=str(document.id),
        original_filename=actual_filename,
        source=actual_source_val,
        status=DocumentStatus.received.value,
    )

    # Execute processing to move document from received -> extracted / needs_review
    try:
        from app.processing import process_document
        processed_doc = process_document(db, document.id)
        if processed_doc:
            document = processed_doc
    except Exception as e:
        logger.warning("Simulated processing error: %s", e)

    return {
        "message": "Kafka input event simulated successfully",
        "event": "documents.ingested",
        "topic": "documents.ingested",
        "source": actual_source_val,
        "document_id": str(document.id),
        "status": document.status.value,
        "kafka_published": event_published,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return document


@router.post("/{document_id}/retry", response_model=DocumentOut)
def retry_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["department_manager", "compliance_officer", "procurement_director"])),
):
    """Requeue an explicitly failed document without duplicating its stored bytes."""
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    if document.status != DocumentStatus.failed:
        raise HTTPException(409, "Only failed documents can be retried")
    db.execute(delete(ExtractedField).where(ExtractedField.document_id == document_id))
    db.execute(delete(DuplicateFlag).where(
        (DuplicateFlag.document_id == document_id)
        | (DuplicateFlag.duplicate_of_document_id == document_id)
    ))
    document.status = DocumentStatus.received
    document.processing_error = None
    document.processed_at = None
    db.commit()
    db.refresh(document)
    publish_event("documents.ingested", str(document.id), {
        "document_id": str(document.id), "source": document.source.value,
        "filename": document.original_filename, "retry": True,
    })
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


@router.get("/watcher/status")
def get_watcher_status():
    """Retrieve the file watcher telemetry — is it running, what has it detected."""
    return get_watcher_telemetry()


@router.get("/storage/buckets")
def list_storage_buckets():
    """List all MinIO buckets and their object counts for the Storage dashboard."""
    from minio import Minio
    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        buckets = []
        for b in client.list_buckets():
            objects = []
            try:
                for obj in client.list_objects(b.name, recursive=True):
                    objects.append({
                        "name": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                        "content_type": obj.content_type,
                        "etag": obj.etag,
                    })
            except Exception:
                pass
            buckets.append({
                "name": b.name,
                "created": b.creation_date.isoformat() if b.creation_date else None,
                "object_count": len(objects),
                "objects": objects,
            })
        return {"buckets": buckets}
    except Exception as e:
        return {"buckets": [], "error": str(e)}


@router.post("/demo/end-to-end")
def run_end_to_end_demo(db: Session = Depends(get_db)):
    """Return a clearly labelled example timeline without creating fake records."""
    from datetime import timezone

    timestamp = datetime.now(timezone.utc).isoformat()
    timeline = [
        ("documents.ingested", "Example: supplier document received", {"source": "shared_folder"}),
        ("documents.processed", "Example: OCR and field extraction completed", {"doc_type": "invoice", "vendor_name": "MedSupply", "total_amount": "41,300"}),
        ("approval.requested", "Example: approval requested", {"approver_role": "department_manager"}),
        ("approval.approved", "Example: approval granted", {"approver": "department_manager"}),
        ("contract.generated", "Example: contract PDF generated after approval", {"template": "supply_agreement"}),
        ("contract.sent_for_signature", "Example: e-signature request would be sent when provider credentials are configured", {"provider": "OpenSign", "status": "example_only"}),
        ("contract.signature_pending", "A real signature is pending; this demo does not send an envelope or claim completion", {"status": "not_sent"}),
    ]
    return {
        "status": "simulation_completed",
        "simulation_only": True,
        "notice": "Illustrative timeline only. No document, approval, email, e-signature envelope, signature, or storage object was created.",
        "total_steps": len(timeline),
        "timeline": [
            {"topic": topic, "message": message, "data": {**data, "simulated": True}, "timestamp": timestamp, "simulated": True}
            for topic, message, data in timeline
        ],
    }

