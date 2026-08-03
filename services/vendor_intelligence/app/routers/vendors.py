import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.kafka_producer import publish_event
from app.kyc import run_onboarding_checks
from app.models import Vendor, VendorDocument, VendorStatus
from app.schemas import VendorCreate, VendorDocumentLink, VendorOut, VendorUpdate

router = APIRouter(prefix="/vendors", tags=["vendors"])

_DECISION_TO_STATUS = {
    "approved": VendorStatus.approved,
    "rejected": VendorStatus.rejected,
    "pending_review": VendorStatus.pending_review,
}


@router.post("", response_model=VendorOut)
def onboard_vendor(payload: VendorCreate, db: Session = Depends(get_db)):
    decision, reasons = run_onboarding_checks(
        legal_name=payload.legal_name,
        vendor_type=payload.vendor_type,
        gst_number=payload.gst_number,
        drug_license_number=payload.drug_license_number,
        drug_license_expiry=payload.drug_license_expiry,
        fda_cdsco_registration_id=payload.fda_cdsco_registration_id,
    )
    vendor = Vendor(
        **payload.model_dump(),
        status=_DECISION_TO_STATUS[decision],
        review_reason="; ".join(reasons) if reasons else None,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    publish_event("vendor.onboarded", str(vendor.id), {
        "vendor_id": str(vendor.id), "status": vendor.status.value, "vendor_type": vendor.vendor_type.value,
    })
    return vendor


@router.get("", response_model=list[VendorOut])
def list_vendors(status: VendorStatus | None = None, db: Session = Depends(get_db)):
    query = select(Vendor).order_by(Vendor.onboarded_at.desc())
    if status:
        query = query.where(Vendor.status == status)
    return db.execute(query).scalars().all()


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: uuid.UUID, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    return vendor


@router.patch("/{vendor_id}", response_model=VendorOut)
def update_vendor(vendor_id: uuid.UUID, payload: VendorUpdate, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vendor, field, value)
    db.commit()
    db.refresh(vendor)
    publish_event("vendor.updated", str(vendor.id), {
        "vendor_id": str(vendor.id), "changed_fields": list(payload.model_dump(exclude_unset=True).keys()),
    })
    return vendor


@router.post("/{vendor_id}/documents", status_code=201)
def link_document(vendor_id: uuid.UUID, payload: VendorDocumentLink, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    link = VendorDocument(vendor_id=vendor_id, document_id=payload.document_id, doc_purpose=payload.doc_purpose)
    db.add(link)
    db.commit()
    return {"linked": True}
