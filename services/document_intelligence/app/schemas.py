import uuid
from datetime import datetime

from pydantic import BaseModel

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
    uploaded_at: datetime
    processed_at: datetime | None
    extracted_fields: list[ExtractedFieldOut] = []

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    id: uuid.UUID
    original_filename: str
    doc_type: DocumentType
    status: DocumentStatus
    uploaded_at: datetime

    class Config:
        from_attributes = True


class FieldCorrection(BaseModel):
    field_value: str
