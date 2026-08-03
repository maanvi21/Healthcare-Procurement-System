import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.kafka_producer import publish_event
from app.minio_client import upload_text
from app.models import Contract, ContractEvent, ContractStatus, ContractTemplate, TemplateType
from app.templates import render


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

    object_key = f"{template_type.value}/{uuid.uuid4()}.html"
    upload_text(object_key, document_html)

    contract = Contract(
        template_id=template.id, vendor_id=vendor_id, request_id=request_id, status=ContractStatus.draft,
        minio_object_key=object_key, version=1, effective_date=effective_date, expiry_date=expiry_date,
        renewal_reminder_days=renewal_reminder_days,
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
