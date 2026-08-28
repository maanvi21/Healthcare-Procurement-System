import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import RequestStatus, StepStatus


class ProcurementRequestCreate(BaseModel):
    requested_by: str
    # Optional: auto-derived from line items when omitted (see service.derive_title), so a
    # request raised automatically from a document still reaches the approver with a label.
    title: str | None = None
    description: str | None = None
    department: str
    category: str
    vendor_id: uuid.UUID | None = None
    vendor_risk_band: str | None = None  # "low" | "medium" | "high" — passed in from the UI/vendor lookup
    items: list[dict] = []  # each item: {"sku": str, "quantity": int, "description": str} — sku is the inventory_intelligence stock item key
    total_value: float
    currency: str = "INR"


class ApprovalStepOut(BaseModel):
    id: uuid.UUID
    step_order: int
    approver_role: str
    approver_id: str | None
    status: StepStatus
    sla_hours: float
    sla_deadline: datetime | None
    decided_at: datetime | None
    decision_note: str | None

    class Config:
        from_attributes = True


class ApprovalHistoryOut(BaseModel):
    event: str
    actor: str
    at: datetime

    class Config:
        from_attributes = True


class ProcurementRequestOut(BaseModel):
    id: uuid.UUID
    requested_by: str
    title: str | None = None
    description: str | None = None
    department: str
    category: str
    vendor_id: uuid.UUID | None
    items: list[dict]
    total_value: float
    currency: str
    status: RequestStatus
    workflow_id: str | None
    created_at: datetime
    steps: list[ApprovalStepOut] = []
    history: list[ApprovalHistoryOut] = []

    class Config:
        from_attributes = True


class DecisionIn(BaseModel):
    step_order: int
    decision: str  # "approved" | "rejected"
    actor: str
    note: str | None = None
