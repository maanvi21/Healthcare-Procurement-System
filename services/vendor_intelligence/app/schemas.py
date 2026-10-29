import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, computed_field

from app.models import RiskBand, VendorStatus, VendorType
from app.kyc import check_gstin


class VendorCreate(BaseModel):
    legal_name: str
    vendor_type: VendorType
    gst_number: str | None = None
    drug_license_number: str | None = None
    drug_license_expiry: date | None = None
    fda_cdsco_registration_id: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = "India"


class VendorUpdate(BaseModel):
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
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
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    status: VendorStatus
    review_reason: str | None
    risk_band: RiskBand | None
    onboarded_at: datetime

    @computed_field
    @property
    def gstin_valid(self) -> bool:
        """Expose the same GSTIN format check used by onboarding and risk scoring."""
        return check_gstin(self.gst_number)[0]

    class Config:
        from_attributes = True


class VendorDocumentLink(BaseModel):
    document_id: uuid.UUID
    doc_purpose: str
