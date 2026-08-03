import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class VendorType(str, enum.Enum):
    equipment_supplier = "equipment_supplier"
    pharma_distributor = "pharma_distributor"
    amc_contractor = "amc_contractor"
    consumables_supplier = "consumables_supplier"


class VendorStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class RiskBand(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_name: Mapped[str] = mapped_column(String(256))
    vendor_type: Mapped[VendorType] = mapped_column(Enum(VendorType, name="vendor_type"))
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    drug_license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    drug_license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    fda_cdsco_registration_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[VendorStatus] = mapped_column(Enum(VendorStatus, name="vendor_status"), default=VendorStatus.pending_review)
    review_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    risk_band: Mapped[RiskBand | None] = mapped_column(Enum(RiskBand, name="vendor_risk_band"), nullable=True)
    onboarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    documents: Mapped[list["VendorDocument"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")


class VendorDocument(Base):
    __tablename__ = "vendor_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))  # cross-service ref -> document_intelligence.documents.id
    doc_purpose: Mapped[str] = mapped_column(String(128))

    vendor: Mapped["Vendor"] = relationship(back_populates="documents")
