import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr

from app.models import RiskBand, VendorStatus, VendorType


class VendorCreate(BaseModel):
    legal_name: str
    vendor_type: VendorType
    gst_number: str | None = None
    drug_license_number: str | None = None
    drug_license_expiry: date | None = None
    fda_cdsco_registration_id: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None


class VendorUpdate(BaseModel):
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    status: VendorStatus | None = None


class VendorOut(BaseModel):
    id: uuid.UUID
    legal_name: str
    vendor_type: VendorType
    gst_number: str | None
    drug_license_number: str | None
    drug_license_expiry: date | None
    fda_cdsco_registration_id: str | None
    contact_email: str | None
    contact_phone: str | None
    status: VendorStatus
    review_reason: str | None
    risk_band: RiskBand | None
    onboarded_at: datetime

    class Config:
        from_attributes = True


class VendorDocumentLink(BaseModel):
    document_id: uuid.UUID
    doc_purpose: str
