import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class DocumentSource(str, enum.Enum):
    upload = "upload"
    email = "email"
    api = "api"
    shared_folder = "shared_folder"


class DocumentType(str, enum.Enum):
    invoice = "invoice"
    purchase_order = "purchase_order"
    quotation = "quotation"
    compliance_certificate = "compliance_certificate"
    vendor_registration = "vendor_registration"
    delivery_note = "delivery_note"
    unclassified = "unclassified"


class DocumentStatus(str, enum.Enum):
    received = "received"
    processing = "processing"
    extracted = "extracted"
    needs_review = "needs_review"
    validated = "validated"
    rejected = "rejected"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[DocumentSource] = mapped_column(Enum(DocumentSource, name="document_source"), default=DocumentSource.upload)
    original_filename: Mapped[str] = mapped_column(String(512))
    minio_object_key: Mapped[str] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, name="document_type"), default=DocumentType.unclassified)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus, name="document_status"), default=DocumentStatus.received)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # mean of OCR and classification confidence — what the review queue thresholds on
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # which engine produced the classification/extraction: "llm" or "rules"
    extraction_engine: Mapped[str] = mapped_column(String(32), default="rules")
    # fraud screen results (see app.fraud)
    fraud_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    fraud_score: Mapped[float] = mapped_column(Float, default=0.0)
    # OCR text kept for audit/traceability of every extracted field; truncated to keep
    # rows a sane size — the full document always remains in MinIO
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON blob: per-stage confidences, fraud flags, missing required fields
    extraction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    field_name: Mapped[str] = mapped_column(String(128))
    field_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_manually_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="extracted_fields")


class DuplicateFlag(Base):
    __tablename__ = "duplicate_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    duplicate_of_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    reason: Mapped[str] = mapped_column(String(256))
