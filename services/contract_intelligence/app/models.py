import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TemplateType(str, enum.Enum):
    supply_agreement = "supply_agreement"
    equipment_amc = "equipment_amc"
    vendor_agreement = "vendor_agreement"
    nda = "nda"


class ContractStatus(str, enum.Enum):
    draft = "draft"
    sent_for_signature = "sent_for_signature"
    signed = "signed"
    declined = "declined"
    expired = "expired"
    terminated = "terminated"


class ContractTemplate(Base):
    __tablename__ = "contract_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    template_type: Mapped[TemplateType] = mapped_column(Enum(TemplateType, name="template_type"))
    body_template: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contract_templates.id"))
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[ContractStatus] = mapped_column(Enum(ContractStatus, name="contract_status"), default=ContractStatus.draft)
    minio_object_key: Mapped[str] = mapped_column(String(512))
    signature_page: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    renewal_reminder_days: Mapped[int] = mapped_column(Integer, default=30)
    esign_envelope_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    signer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    signer_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    signing_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    signing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    certificate_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    template: Mapped[ContractTemplate] = relationship(lazy="joined")
    events: Mapped[list["ContractEvent"]] = relationship(back_populates="contract", cascade="all, delete-orphan", order_by="ContractEvent.at")

    @property
    def template_type(self) -> TemplateType:
        return self.template.template_type


class ContractEvent(Base):
    __tablename__ = "contract_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"))
    event: Mapped[str] = mapped_column(String(128))
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contract: Mapped["Contract"] = relationship(back_populates="events")
