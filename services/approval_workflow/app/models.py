import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    escalated = "escalated"


class StepStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    escalated = "escalated"
    skipped = "skipped"


class ProcurementRequest(Base):
    __tablename__ = "procurement_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_by: Mapped[str] = mapped_column(String(128))
    # What the approver is actually being asked to approve. Without these the inbox could
    # only show department/value/step, so an approver had to decide on a bare rupee amount
    # with no idea what was being bought — auto-filled from the source document or the
    # line items when the requester does not supply one (see service.derive_title).
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(128))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    items: Mapped[list] = mapped_column(JSONB, default=list)
    total_value: Mapped[float] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus, name="request_status"), default=RequestStatus.pending)
    workflow_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # the document_intelligence document that triggered this request (null when raised by
    # hand in the UI). Unique, so Kafka redelivery cannot raise the same request twice.
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    steps: Mapped[list["ApprovalStep"]] = relationship(back_populates="request", cascade="all, delete-orphan", order_by="ApprovalStep.step_order")
    history: Mapped[list["ApprovalHistory"]] = relationship(back_populates="request", cascade="all, delete-orphan", order_by="ApprovalHistory.at")


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("procurement_requests.id"))
    step_order: Mapped[int] = mapped_column()
    approver_role: Mapped[str] = mapped_column(String(128))
    approver_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus, name="step_status"), default=StepStatus.pending)
    sla_hours: Mapped[float] = mapped_column(default=24)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped["ProcurementRequest"] = relationship(back_populates="steps")


class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("procurement_requests.id"))
    event: Mapped[str] = mapped_column(String(128))
    actor: Mapped[str] = mapped_column(String(128))
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    request: Mapped["ProcurementRequest"] = relationship(back_populates="history")
