import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
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
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        address_line1=payload.address_line1,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country=payload.country,
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


@router.get("/resolve")
def resolve_vendor(legal_name: str, db: Session = Depends(get_db)):
    """Resolve a vendor name (as OCR'd off a document) to a vendor id.

    Document intelligence extracts a vendor *name* from an invoice; every downstream
    service keys off a vendor *id*. This is the seam between the two.

    Matching is deliberately conservative — exact (case-insensitive) first, then a
    prefix/substring match, and only if that yields exactly one candidate. OCR'd vendor
    names are noisy, and silently attaching an invoice to the wrong supplier is far worse
    than leaving `vendor_id` null and letting a human resolve it in the review queue.
    Returns `{vendor_id: null}` rather than 404 when nothing matches confidently, so the
    caller can treat "no confident match" as a normal outcome.
    """
    # OCR routinely adds or drops trailing punctuation — a scanned "MediPharma Pvt Ltd."
    # must still match the "MediPharma Pvt Ltd" on file, or every scanned invoice from a
    # known supplier lands unattributed in the review queue.
    cleaned = " ".join(legal_name.split()).strip().strip(".,;:-–—|/\\ ")
    if len(cleaned) < 3:
        return {"vendor_id": None, "match": "none", "reason": "name too short to match on"}

    # compare both sides with trailing punctuation removed, so the stored name having a
    # period (or not) is equally forgiving
    normalised = func.rtrim(func.lower(Vendor.legal_name), ".,;:- ")
    exact = db.execute(
        select(Vendor).where(normalised == cleaned.lower())
    ).scalars().all()
    if len(exact) == 1:
        return {"vendor_id": str(exact[0].id), "legal_name": exact[0].legal_name, "match": "exact"}
    if len(exact) > 1:
        return {"vendor_id": None, "match": "ambiguous", "reason": f"{len(exact)} vendors share this legal name"}

    fuzzy = db.execute(
        select(Vendor).where(Vendor.legal_name.ilike(f"%{cleaned}%"))
    ).scalars().all()
    if not fuzzy:
        # try the other direction: OCR often appends junk ("Ltd. | Invoice") to the name
        head = cleaned.split(",")[0][:64]
        if len(head) >= 4:
            fuzzy = db.execute(
                select(Vendor).where(Vendor.legal_name.ilike(f"{head}%"))
            ).scalars().all()

    if len(fuzzy) == 1:
        return {"vendor_id": str(fuzzy[0].id), "legal_name": fuzzy[0].legal_name, "match": "fuzzy"}
    if len(fuzzy) > 1:
        return {"vendor_id": None, "match": "ambiguous", "reason": f"{len(fuzzy)} candidate vendors"}
    return {"vendor_id": None, "match": "none", "reason": "no vendor matched"}


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
