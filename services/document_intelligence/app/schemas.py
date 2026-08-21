import json
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models import DocumentSource, DocumentStatus, DocumentType


class ExtractedFieldOut(BaseModel):
    id: uuid.UUID
    field_name: str
    field_value: str
    confidence: float
    is_manually_corrected: bool

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: uuid.UUID
    source: DocumentSource
    original_filename: str
    doc_type: DocumentType
    status: DocumentStatus
    vendor_id: uuid.UUID | None
    classification_confidence: float
    ocr_confidence: float
    overall_confidence: float
    extraction_engine: str
    fraud_flag: bool
    fraud_score: float
    uploaded_at: datetime
    processed_at: datetime | None
    extracted_fields: list[ExtractedFieldOut] = []
    extraction_notes: dict = {}

    @field_validator("extraction_notes", mode="before")
    @classmethod
    def _parse_notes(cls, value):
        """`extraction_notes` is stored as a JSON string; expose it as an object."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return value or {}

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    id: uuid.UUID
    original_filename: str
    doc_type: DocumentType
    status: DocumentStatus
    overall_confidence: float
    fraud_flag: bool
    fraud_score: float
    uploaded_at: datetime

    class Config:
        from_attributes = True


class FieldCorrection(BaseModel):
    field_value: str


class DocumentReview(BaseModel):
    """Payload for a document-level manual review (`PUT /documents/{id}/review`)."""

    doc_type: DocumentType | None = None
    fields: dict[str, str] = {}
    fraud_flag: bool | None = None
    status: DocumentStatus | None = None
    # set explicitly to attach a vendor by id; if omitted and a corrected vendor_name is
    # supplied, the service re-runs name-based resolution against vendor_intelligence
    vendor_id: uuid.UUID | None = None
