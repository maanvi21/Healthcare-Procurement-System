import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models import ContractStatus, TemplateType


class TemplateCreate(BaseModel):
    name: str
    template_type: TemplateType
    body_template: str
    version: int = 1


class TemplateOut(TemplateCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True


class ContractGenerate(BaseModel):
    template_type: TemplateType
    vendor_id: uuid.UUID
    request_id: uuid.UUID | None = None
    context: dict  # rendered into the Jinja2 template: vendor_name, hospital_name, items, total_value, payment_terms, ...
    effective_date: date
    expiry_date: date
    renewal_reminder_days: int = 30


class ContractEventOut(BaseModel):
    event: str
    at: datetime

    class Config:
        from_attributes = True


class ContractOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    vendor_id: uuid.UUID
    request_id: uuid.UUID | None
    status: ContractStatus
    template_type: TemplateType
    minio_object_key: str
    signature_page: int
    version: int
    effective_date: date | None
    expiry_date: date | None
    renewal_reminder_days: int
    esign_envelope_id: str | None
    signing_url: str | None
    signer_name: str | None
    signer_email: str | None
    signing_provider: str | None
    signing_error: str | None
    signed_object_key: str | None
    certificate_object_key: str | None
    created_at: datetime
    events: list[ContractEventOut] = []

    class Config:
        from_attributes = True
