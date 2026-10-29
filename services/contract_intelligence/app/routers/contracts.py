import uuid
import hashlib
import hmac
from urllib.parse import urlparse
from datetime import date, timedelta

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.config import settings
from app.kafka_producer import publish_event
from app.minio_client import download_bytes, upload_bytes
from app.models import Contract, ContractEvent, ContractStatus, ContractTemplate
from app.opa_client import check_signature_allowed
from app.schemas import ContractGenerate, ContractOut, TemplateCreate, TemplateOut
from app.service import dispatch_signature, generate_contract

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
def get_contract_document(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["department_manager", "finance_manager", "compliance_officer", "procurement_director"])),
):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")
    return Response(
        download_bytes(contract.minio_object_key),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="contract-{contract.id}.pdf"'},
    )


@router.get("/{contract_id}/signed-document")
def get_signed_contract_document(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["department_manager", "finance_manager", "compliance_officer", "procurement_director"])),
):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, "Contract not found")
    if contract.status != ContractStatus.signed or not contract.signed_object_key:
        raise HTTPException(404, "Signed PDF is not available yet")
    return Response(
        download_bytes(contract.signed_object_key),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="signed-contract-{contract.id}.pdf"'},
    )


@router.post("/{contract_id}/send-for-signature", response_model=ContractOut)
def send_contract_for_signature(
    contract_id: uuid.UUID, signer_email: str, signer_name: str,
    vendor_risk_band: str | None = None, drug_license_valid: bool = True, override_approved: bool = False,
    db: Session = Depends(get_db),
    role: str = Depends(require_roles(["compliance_officer", "procurement_director"])),
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

    try:
        return dispatch_signature(db, contract, signer_email, signer_name)
    except Exception as exc:
        contract.signing_error = str(exc)[:4000]
        db.commit()
        raise HTTPException(502, f"Could not send contract through the e-signature provider: {exc}")


@router.post("/webhooks/opensign")
async def opensign_webhook(request: Request, db: Session = Depends(get_db)):
    """Verify OpenSign's HMAC callback and archive its completed PDF/certificate."""
    if not settings.opensign_webhook_secret:
        raise HTTPException(503, "OpenSign webhook secret is not configured")
    raw = await request.body()
    received = request.headers.get("x-webhook-signature", "")
    expected = hmac.new(settings.opensign_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(received, expected):
        raise HTTPException(401, "Invalid OpenSign webhook signature")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid webhook JSON")
    envelope_id = payload.get("objectId")
    contract = db.execute(select(Contract).where(Contract.esign_envelope_id == envelope_id)).scalars().first()
    if not contract:
        raise HTTPException(404, "Contract envelope not found")

    event = (payload.get("event") or "").lower()
    if event == "declined":
        contract.status = ContractStatus.declined
        contract.signing_error = payload.get("declinedReason")
        db.add(ContractEvent(contract_id=contract.id, event="declined"))
        db.commit()
        return {"status": "declined", "contract_id": str(contract.id)}
    if event != "completed":
        db.add(ContractEvent(contract_id=contract.id, event=event or "provider_event"))
        db.commit()
        return {"status": event or "accepted"}

    allowed_hosts = [x.strip().lower() for x in settings.opensign_file_hosts.split(",") if x.strip()]
    def fetch_provider_file(url: str | None) -> bytes | None:
        if not url:
            return None
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not any(host == suffix or host.endswith("." + suffix) for suffix in allowed_hosts):
            raise HTTPException(400, "OpenSign artifact URL host is not allowed; configure OPENSIGN_FILE_HOSTS.")
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(64 * 1024):
            size += len(chunk)
            if size > 25 * 1024 * 1024:
                raise HTTPException(413, "OpenSign artifact exceeds 25 MB")
            chunks.append(chunk)
        return b"".join(chunks)

    try:
        signed_pdf = fetch_provider_file(payload.get("file"))
        certificate = fetch_provider_file(payload.get("certificate"))
    except requests.RequestException as exc:
        raise HTTPException(502, f"Could not retrieve signed OpenSign artifact: {exc}")
    if not signed_pdf:
        raise HTTPException(400, "Completed event did not include the signed PDF")
    contract.signed_object_key = f"signed/{contract.id}/{uuid.uuid4()}.pdf"
    upload_bytes(contract.signed_object_key, signed_pdf)
    if certificate:
        contract.certificate_object_key = f"certificates/{contract.id}/{uuid.uuid4()}.pdf"
        upload_bytes(contract.certificate_object_key, certificate)
    contract.status = ContractStatus.signed
    contract.signing_error = None
    db.add(ContractEvent(contract_id=contract.id, event="signed"))
    db.commit()
    publish_event("contract.signed", str(contract.id), {
        "contract_id": str(contract.id), "vendor_id": str(contract.vendor_id),
        "signer_email": contract.signer_email, "signed_document_available": True,
    })
    return {"status": "signed", "contract_id": str(contract.id)}
