import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.esign_client import send_for_signature
from app.kafka_producer import publish_event
from app.minio_client import download_text
from app.models import Contract, ContractEvent, ContractStatus, ContractTemplate
from app.opa_client import check_signature_allowed
from app.schemas import ContractGenerate, ContractOut, TemplateCreate, TemplateOut
from app.service import generate_contract

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("/templates", response_model=TemplateOut)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["procurement_director"])),
):
    template = ContractTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return db.execute(select(ContractTemplate)).scalars().all()


@router.post("", response_model=ContractOut)
def create_contract(
    payload: ContractGenerate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["procurement_director"])),
):
    try:
        contract = generate_contract(
            db, payload.template_type, payload.vendor_id, payload.request_id, payload.context,
            payload.effective_date, payload.expiry_date, payload.renewal_reminder_days,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return contract


@router.get("", response_model=list[ContractOut])
def list_contracts(status: ContractStatus | None = None, db: Session = Depends(get_db)):
    query = select(Contract).order_by(Contract.created_at.desc())
    if status:
        query = query.where(Contract.status == status)
    return db.execute(query).scalars().all()


@router.get("/expiring", response_model=list[ContractOut])
def expiring_contracts(within_days: int = 30, db: Session = Depends(get_db)):
    cutoff = date.today() + timedelta(days=within_days)
    query = select(Contract).where(Contract.expiry_date <= cutoff, Contract.status == ContractStatus.signed)
    return db.execute(query).scalars().all()


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract(contract_id: uuid.UUID, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")
    return contract


@router.get("/{contract_id}/document")
def get_contract_document(contract_id: uuid.UUID, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")
    return {"html": download_text(contract.minio_object_key)}


@router.post("/{contract_id}/send-for-signature", response_model=ContractOut)
def send_contract_for_signature(
    contract_id: uuid.UUID, signer_email: str, signer_name: str,
    vendor_risk_band: str | None = None, drug_license_valid: bool = True, override_approved: bool = False,
    db: Session = Depends(get_db),
    role: str = Depends(require_roles(["procurement_director"])),
):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")

    if override_approved and role not in ("compliance_officer", "procurement_director"):
        raise HTTPException(
            403,
            detail=f"Access denied for role '{role}'. Required: ['compliance_officer', 'procurement_director']",
        )

    allowed, reasons = check_signature_allowed(vendor_risk_band, drug_license_valid, override_approved)
    if not allowed:
        raise HTTPException(403, {"message": "Blocked by compliance policy", "reasons": reasons})

    document_html = download_text(contract.minio_object_key)
    envelope_id = send_for_signature(str(contract.id), document_html, signer_email, signer_name)
    contract.esign_envelope_id = envelope_id
    contract.status = ContractStatus.sent_for_signature
    db.add(ContractEvent(contract_id=contract.id, event="sent_for_signature"))
    db.commit()
    db.refresh(contract)
    return contract


@router.post("/{contract_id}/webhook/signed", response_model=ContractOut)
def contract_signed_webhook(contract_id: uuid.UUID, db: Session = Depends(get_db)):
    """Simulates the callback an e-signature provider would POST once all parties have
    signed. A real OpenSign deployment would call this exact endpoint via a configured
    webhook."""
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")
    contract.status = ContractStatus.signed
    db.add(ContractEvent(contract_id=contract.id, event="signed"))
    db.commit()
    db.refresh(contract)
    publish_event("contract.signed", str(contract.id), {"contract_id": str(contract.id), "vendor_id": str(contract.vendor_id)})
    return contract
