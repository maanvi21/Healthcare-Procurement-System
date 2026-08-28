"""Core notification send / digest helpers."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels import send_stub
from app.config import settings
from app.models import Notification, NotificationStatus, NotificationTemplate
from app.templates import render


def resolve_recipient(data: dict) -> str:
    for key in ("contact_email", "email", "recipient", "notify_email", "phone", "contact_phone"):
        value = data.get(key)
        if value:
            return str(value)
    return settings.default_notification_recipient


def send_from_template(
    db: Session,
    template: NotificationTemplate,
    context: dict,
    *,
    recipient: str | None = None,
    event_key: str | None = None,
) -> Notification:
    ctx = {**context}
    recipient = recipient or resolve_recipient(ctx)
    subject = render(template.subject_template, ctx) if template.subject_template else None
    body = render(template.body_template, ctx)

    notification = Notification(
        template_id=template.id,
        channel=template.channel,
        recipient=recipient,
        subject=subject,
        body=body,
        event_type=template.event_type,
        event_key=event_key,
        status=NotificationStatus.queued,
    )
    db.add(notification)
    db.flush()

    try:
        send_stub(template.channel, recipient, subject, body)
        notification.status = NotificationStatus.sent
    except Exception:
        notification.status = NotificationStatus.failed
        raise
    finally:
        db.commit()
        db.refresh(notification)

    return notification


def send_direct(
    db: Session,
    *,
    channel,
    recipient: str,
    body: str,
    subject: str | None = None,
    event_type: str | None = None,
    event_key: str | None = None,
) -> Notification:
    notification = Notification(
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=body,
        event_type=event_type,
        event_key=event_key,
        status=NotificationStatus.queued,
    )
    db.add(notification)
    db.flush()
    try:
        send_stub(channel, recipient, subject, body)
        notification.status = NotificationStatus.sent
    except Exception:
        notification.status = NotificationStatus.failed
        raise
    finally:
        db.commit()
        db.refresh(notification)
    return notification


def handle_event(db: Session, event_type: str, data: dict) -> list[Notification]:
    templates = db.execute(
        select(NotificationTemplate).where(NotificationTemplate.event_type == event_type)
    ).scalars().all()
    if not templates:
        return []

    event_key = str(
        data.get("request_id")
        or data.get("document_id")
        or data.get("vendor_id")
        or data.get("contract_id")
        or data.get("id")
        or ""
    ) or None

    sent: list[Notification] = []
    for template in templates:
        sent.append(send_from_template(db, template, data, event_key=event_key))
    return sent


def build_digest(db: Session, recipient: str, hours: int = 24) -> tuple[list[Notification], str]:
    since = datetime.utcnow() - timedelta(hours=max(1, hours))
    rows = db.execute(
        select(Notification)
        .where(Notification.recipient == recipient, Notification.created_at >= since)
        .order_by(Notification.created_at.desc())
    ).scalars().all()

    if not rows:
        summary = f"No notifications for {recipient} in the last {hours} hour(s)."
        return [], summary

    lines = [f"Digest for {recipient} — {len(rows)} notification(s) in the last {hours} hour(s):"]
    for n in rows:
        stamp = n.created_at.isoformat(timespec="seconds") if n.created_at else "?"
        subject = n.subject or n.event_type or n.channel.value
        lines.append(f"- [{stamp}] {n.channel.value} · {subject}: {n.body[:160]}")
    return list(rows), "\n".join(lines)
