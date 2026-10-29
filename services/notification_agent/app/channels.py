"""Email-only notification delivery through SendGrid."""
import logging
import os
import re

from email_validator import EmailNotValidError, validate_email

from app.config import settings
from app.models import NotificationChannel

logger = logging.getLogger("notification_agent.channels")
_PLACEHOLDER_VALUE = re.compile(
    r"your[-_ ]|placeholder|example|change[-_ ]?me|replace[-_ ]?me|<[^>]+>|x{6,}|(?:T|B)0{5,}",
    re.IGNORECASE,
)

PROVIDER_ENV = {
    "email": ("SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL"),
}


class NotificationSendError(RuntimeError):
    """Raised after a configured channel fails to deliver a notification."""


def _required_env(*names: str) -> dict[str, str] | None:
    values = {name: os.getenv(name, "").strip() for name in names}
    if any(not value or _PLACEHOLDER_VALUE.search(value) for value in values.values()):
        return None
    return values


def get_provider_status() -> dict[str, dict[str, str | bool]]:
    """Expose email readiness without returning secrets or recipient addresses."""
    configured = _required_env(*PROVIDER_ENV["email"]) is not None
    fallback_recipient = _normalized_email(settings.default_notification_recipient)
    return {
        "email": {
            "configured": configured,
            "state": "ready" if configured else "simulated",
            "fallback_recipient_configured": fallback_recipient is not None,
        }
    }


def _normalized_email(value: str | None) -> str | None:
    candidate = (value or "").strip()
    if not candidate:
        return None
    try:
        return validate_email(candidate, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def _send_email(recipient: str, subject: str | None, body: str, config: dict[str, str]) -> None:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=(config["SENDGRID_FROM_EMAIL"], "MediSource AI"),
            to_emails=recipient,
            subject=subject or "Notification",
            plain_text_content=body,
        )
        response = SendGridAPIClient(config["SENDGRID_API_KEY"]).send(message)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"SendGrid returned HTTP {response.status_code}: {response.body}")
    except Exception as exc:
        raise NotificationSendError(f"email delivery failed: {exc}") from exc


def send_notification(channel: NotificationChannel, recipient: str, subject: str | None, body: str) -> bool:
    """Return True only for a real provider delivery; False means log-only simulation."""
    try:
        if channel != NotificationChannel.email:
            raise NotificationSendError("Only email notifications are supported.")
        recipient = _normalized_email(recipient)
        if recipient is None:
            raise NotificationSendError(
                "A valid recipient email is required. Set DEFAULT_NOTIFICATION_RECIPIENT "
                "or provide an email address in the event."
            )
        config = _required_env("SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL")
        if config is None:
            logger.warning("Email provider credentials are missing or placeholders; recording as simulated")
            send_stub(channel, recipient, subject, body)
            return False
        _send_email(recipient, subject, body, config)
        return True
    except NotificationSendError as exc:
        logger.error("Notification delivery failed for %s: %s", channel.value, exc)
        raise
    return False


def send_stub(channel: NotificationChannel, recipient: str, subject: str | None, body: str) -> None:
    logger.info(
        "[STUB %s] to=%s subject=%s body=%s",
        channel.value.upper(),
        recipient,
        subject or "(none)",
        body[:500] + ("…" if len(body) > 500 else ""),
    )
