"""Core notification send / digest helpers."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
import requests

from app.channels import send_notification
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
    if recipient is None and template.recipient_template:
        recipient = render(template.recipient_template, ctx).strip()
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
    if event_key:
        existing = db.execute(
            select(Notification).where(
                Notification.template_id == template.id,
                Notification.recipient == recipient,
                Notification.event_key == event_key,
            )
        ).scalars().first()
        if existing:
            return existing
    db.add(notification)
    db.flush()

    try:
        notification.status = NotificationStatus.sent if send_notification(template.channel, recipient, subject, body) else NotificationStatus.simulated
    except Exception as exc:
        notification.status = NotificationStatus.failed
        notification.failure_reason = str(exc)[:2000]
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
        notification.status = NotificationStatus.sent if send_notification(channel, recipient, subject, body) else NotificationStatus.simulated
    except Exception as exc:
        notification.status = NotificationStatus.failed
        notification.failure_reason = str(exc)[:2000]
    finally:
        db.commit()
        db.refresh(notification)
    return notification


def handle_event(db: Session, event_type: str, data: dict) -> list[Notification]:
    templates = db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.is_active.is_(True),
        )
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
    recipients = []
    if data.get("approver_email"):
        recipients.append(str(data["approver_email"]))
    if data.get("requester_email"):
        recipients.append(str(data["requester_email"]))
    if event_type in {"approval.approved", "approval.rejected"} and data.get("vendor_id"):
        try:
            response = requests.get(
                f"{settings.vendor_intelligence_url.rstrip('/')}/vendors/{data['vendor_id']}",
                timeout=4,
            )
            response.raise_for_status()
            vendor_email = response.json().get("contact_email")
            if vendor_email:
                recipients.append(str(vendor_email))
        except requests.RequestException:
            # The event is retained; a configured fallback recipient still receives it.
            pass
    recipients = list(dict.fromkeys(email for email in recipients if email))
    for template in templates:
        target_recipients = recipients or [None]
        for recipient in target_recipients:
            if template.recipient_template:
                # A recipient expression is specific to its event payload (for example
                # approver_email) and should not be overwritten by outcome fan-out.
                target = render(template.recipient_template, data).strip()
                if target:
                    sent.append(send_from_template(db, template, data, recipient=target, event_key=event_key))
                break
            sent.append(send_from_template(db, template, data, recipient=recipient, event_key=event_key))
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
