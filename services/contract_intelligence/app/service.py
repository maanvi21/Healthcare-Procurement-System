import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.kafka_producer import publish_event
from app.minio_client import download_bytes, upload_bytes
from app.models import Contract, ContractEvent, ContractStatus, ContractTemplate, TemplateType
from app.pdf_render import render_contract_pdf
from app.templates import render
from app.esign_client import send_for_signature


def generate_contract(
    db: Session, template_type: TemplateType, vendor_id, request_id, context: dict,
    effective_date: date, expiry_date: date, renewal_reminder_days: int = 30,
) -> Contract:
    template = db.query(ContractTemplate).filter(ContractTemplate.template_type == template_type).order_by(ContractTemplate.version.desc()).first()
    if not template:
        raise ValueError(f"No template seeded for {template_type}")

    render_context = {
        "effective_date": effective_date.isoformat(), "expiry_date": expiry_date.isoformat(),
        "renewal_reminder_days": renewal_reminder_days, **context,
    }
    document_html = render(template.body_template, render_context)
    pdf_bytes, signature_page = render_contract_pdf(document_html, context.get("vendor_name", "Supplier"))
    object_key = f"{template_type.value}/{uuid.uuid4()}.pdf"
    upload_bytes(object_key, pdf_bytes)

    contract = Contract(
        template_id=template.id, vendor_id=vendor_id, request_id=request_id, status=ContractStatus.draft,
        minio_object_key=object_key, signature_page=signature_page, version=1, effective_date=effective_date, expiry_date=expiry_date,
        renewal_reminder_days=renewal_reminder_days,
        signing_error=None,
    )
    db.add(contract)
    db.flush()
    db.add(ContractEvent(contract_id=contract.id, event="generated"))
    db.commit()
    db.refresh(contract)

    publish_event("contract.generated", str(contract.id), {
        "contract_id": str(contract.id), "vendor_id": str(vendor_id),
    })
    return contract


def dispatch_signature(db: Session, contract: Contract, signer_email: str, signer_name: str) -> Contract:
    pdf_bytes = download_bytes(contract.minio_object_key)
    result = send_for_signature(
        str(contract.id), pdf_bytes, signer_email, signer_name, contract.signature_page,
    )
    contract.esign_envelope_id = result["object_id"]
    contract.signing_url = result.get("signing_url")
    contract.signer_name = signer_name
    contract.signer_email = signer_email
    contract.signing_provider = result["provider"]
    contract.signing_error = None
    contract.status = ContractStatus.sent_for_signature
    db.add(ContractEvent(contract_id=contract.id, event="sent_for_signature"))
    db.commit()
    db.refresh(contract)
    publish_event("contract.sent_for_signature", str(contract.id), {
        "contract_id": str(contract.id), "vendor_id": str(contract.vendor_id),
        "signer_email": signer_email, "signing_provider": contract.signing_provider,
    })
    return contract
