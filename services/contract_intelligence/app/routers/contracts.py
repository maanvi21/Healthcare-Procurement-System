import uuid
import hashlib
import hmac
import base64
import json
import logging
import xml.etree.ElementTree as ET
from datetime import date, timedelta

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
from app.esign_client import credentials_configured, connect_configured, download_completed_documents

router = APIRouter(prefix="/contracts", tags=["contracts"])
logger = logging.getLogger("contract_intelligence.contracts")


@router.get("/signing-status")
def signing_configuration_status(
    _role: str = Depends(require_roles(["department_manager", "finance_manager", "compliance_officer", "procurement_director"])),
):
    """Expose integration readiness to the CPanel without exposing provider secrets."""
    token_ready = credentials_configured()
    webhook_ready = connect_configured()
    return {
        "provider": "DocuSign",
        "email_invites_enabled": token_ready,
        "completion_tracking_enabled": webhook_ready,
        "ready": token_ready and webhook_ready,
    }


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
    try:
        content = download_bytes(contract.minio_object_key)
    except Exception as exc:
        raise HTTPException(503, "Contract PDF could not be loaded from object storage. Verify MinIO is healthy and the contracts bucket is available.") from exc
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="contract-{contract.id}.pdf"', "Cache-Control": "no-store"},
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
    try:
        content = download_bytes(contract.signed_object_key)
    except Exception as exc:
        raise HTTPException(503, "Signed contract could not be loaded from object storage. Verify MinIO is healthy and the contracts bucket is available.") from exc
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="signed-contract-{contract.id}.pdf"', "Cache-Control": "no-store"},
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


def parse_docusign_event(raw: bytes) -> tuple[str | None, str]:
    """Read Connect JSON SIM, legacy JSON, or legacy XML messages."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        payload = None
    if isinstance(payload, dict):
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        envelope_summary = data.get("envelopeSummary") or {}
        if not isinstance(envelope_summary, dict):
            envelope_summary = {}
        envelope_id = data.get("envelopeId") or payload.get("envelopeId") or envelope_summary.get("envelopeId")
        event = str(payload.get("event") or envelope_summary.get("status") or payload.get("status") or "").lower()
        if envelope_id:
            return str(envelope_id), event
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        if isinstance(payload, dict):
            envelope_status = payload.get("EnvelopeStatus") or {}
            return envelope_status.get("EnvelopeID"), str(envelope_status.get("Status") or "").lower()
        raise HTTPException(400, "Invalid DocuSign Connect payload")

    def local_text(name: str) -> str | None:
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1].lower() == name.lower() and element.text:
                return element.text.strip()
        return None

    return local_text("EnvelopeID"), (local_text("Status") or "").lower()


@router.post("/webhooks/docusign")
async def docusign_webhook(request: Request, db: Session = Depends(get_db)):
    """Verify DocuSign Connect HMAC, update lifecycle state, and archive completed files."""
    secret = (settings.docusign_connect_hmac_key or "").strip()
    if not secret:
        raise HTTPException(503, "DocuSign Connect HMAC key is not configured")
    raw = await request.body()
    expected = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode("ascii")
    signatures = [
        value for key, value in request.headers.items()
        if key.lower().startswith("x-docusign-signature-")
    ]
    if not any(hmac.compare_digest(value, expected) for value in signatures):
        raise HTTPException(401, "Invalid DocuSign Connect signature")
    envelope_id, event = parse_docusign_event(raw)
    if not envelope_id:
        raise HTTPException(400, "DocuSign Connect event does not include an envelope ID")
    contract = db.execute(select(Contract).where(Contract.esign_envelope_id == envelope_id)).scalars().first()
    if not contract:
        raise HTTPException(404, "DocuSign envelope is not associated with a contract")

    if event in {"envelope-declined", "declined"}:
        contract.status = ContractStatus.declined
        contract.signing_error = "Signer declined the DocuSign envelope."
        db.add(ContractEvent(contract_id=contract.id, event="declined"))
        db.commit()
        return {"status": "declined", "contract_id": str(contract.id)}
    if event in {"envelope-voided", "voided"}:
        contract.status = ContractStatus.terminated
        contract.signing_error = "DocuSign envelope was voided."
        db.add(ContractEvent(contract_id=contract.id, event="voided"))
        db.commit()
        return {"status": "voided", "contract_id": str(contract.id)}
    if event not in {"envelope-completed", "completed"}:
        db.add(ContractEvent(contract_id=contract.id, event=event or "provider_event"))
        db.commit()
        return {"status": event or "accepted", "contract_id": str(contract.id)}

    try:
        signed_pdf, certificate = download_completed_documents(envelope_id)
        contract.signed_object_key = f"signed/{contract.id}/{uuid.uuid4()}.pdf"
        upload_bytes(contract.signed_object_key, signed_pdf)
        if certificate:
            contract.certificate_object_key = f"certificates/{contract.id}/{uuid.uuid4()}.pdf"
            upload_bytes(contract.certificate_object_key, certificate)
        contract.status = ContractStatus.signed
        contract.signing_error = None
        db.add(ContractEvent(contract_id=contract.id, event="signed"))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Could not archive completed DocuSign envelope %s", envelope_id)
        raise HTTPException(502, "DocuSign reported completion, but the signed PDF could not be archived. Connect can retry this event.") from exc
    publish_event("contract.signed", str(contract.id), {
        "contract_id": str(contract.id), "vendor_id": str(contract.vendor_id),
        "signer_email": contract.signer_email, "signed_document_available": True,
    })
    return {"status": "signed", "contract_id": str(contract.id)}
