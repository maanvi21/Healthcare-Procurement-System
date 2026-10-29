import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import require_roles
from app.models import Notification, NotificationTemplate
from app.schemas import DigestOut, NotificationOut, SendRequest, TemplateCreate, TemplateOut, TemplateUpdate
from app.service import build_digest, send_direct
from app.channels import get_provider_status

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/provider-status")
def provider_status():
    """Report provider readiness without exposing keys or webhook URLs."""
    return get_provider_status()


@router.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db), _role: str = Depends(require_roles(["procurement_director"]))):
    template = NotificationTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return db.execute(select(NotificationTemplate).order_by(NotificationTemplate.created_at.desc())).scalars().all()


@router.put("/templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: uuid.UUID, payload: TemplateUpdate, db: Session = Depends(get_db), _role: str = Depends(require_roles(["procurement_director"]))):
    template = db.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}")
def delete_template(template_id: uuid.UUID, db: Session = Depends(get_db), _role: str = Depends(require_roles(["procurement_director"]))):
    template = db.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    template.is_active = False
    db.commit()
    return {"disabled": str(template_id)}


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    recipient: str | None = None,
    event_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if recipient:
        stmt = stmt.where(Notification.recipient == recipient)
    if event_type:
        stmt = stmt.where(Notification.event_type == event_type)
    return db.execute(stmt).scalars().all()


@router.post("/send", response_model=NotificationOut)
def send_notification(payload: SendRequest, db: Session = Depends(get_db)):
    return send_direct(
        db,
        channel=payload.channel,
        recipient=payload.recipient,
        subject=payload.subject,
        body=payload.body,
        event_type=payload.event_type,
        event_key=payload.event_key,
    )


@router.get("/digest", response_model=DigestOut)
def digest(
    recipient: str,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    rows, summary = build_digest(db, recipient, hours=hours)
    return DigestOut(
        recipient=recipient,
        hours=hours,
        count=len(rows),
        summary=summary,
        notifications=rows,
    )
