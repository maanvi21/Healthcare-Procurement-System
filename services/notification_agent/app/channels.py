"""Multi-channel notification senders with per-channel stub fallbacks."""
import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.models import NotificationChannel

logger = logging.getLogger("notification_agent.channels")
_PLACEHOLDER_VALUE = re.compile(
    r"your[-_ ]|placeholder|example|change[-_ ]?me|replace[-_ ]?me|<[^>]+>|x{6,}|(?:T|B)0{5,}",
    re.IGNORECASE,
)

PROVIDER_ENV = {
    "email": ("SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL"),
    "sms": ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"),
    "teams": ("TEAMS_WEBHOOK_URL",),
    "slack": ("SLACK_WEBHOOK_URL",),
}


class NotificationSendError(RuntimeError):
    """Raised after a configured channel fails to deliver a notification."""


def _required_env(*names: str) -> dict[str, str] | None:
    values = {name: os.getenv(name, "").strip() for name in names}
    if any(not value or _PLACEHOLDER_VALUE.search(value) for value in values.values()):
        return None
    return values


def get_provider_status() -> dict[str, dict[str, str | bool]]:
    """Expose channel readiness without returning secrets or webhook URLs."""
    status = {}
    for channel, names in PROVIDER_ENV.items():
        configured = _required_env(*names) is not None
        status[channel] = {
            "configured": configured,
            "state": "ready" if configured else "simulated",
        }
    return status


def _send_webhook(channel: str, url: str, body: str, subject: str | None) -> None:
    payload = {"text": f"{subject}\n{body}" if subject else body}
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"HTTP {response.status}")
    except (HTTPError, URLError, OSError, RuntimeError) as exc:
        raise NotificationSendError(f"{channel} webhook delivery failed: {exc}") from exc


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


def _send_sms(recipient: str, body: str, config: dict[str, str]) -> None:
    try:
        from twilio.rest import Client

        Client(config["TWILIO_ACCOUNT_SID"], config["TWILIO_AUTH_TOKEN"]).messages.create(
            body=body,
            from_=config["TWILIO_FROM_NUMBER"],
            to=recipient,
        )
    except Exception as exc:
        raise NotificationSendError(f"SMS delivery failed: {exc}") from exc


def send_notification(channel: NotificationChannel, recipient: str, subject: str | None, body: str) -> bool:
    """Return True only for a real provider delivery; False means log-only simulation."""
    try:
        if channel == NotificationChannel.email:
            config = _required_env("SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL")
            if config is None:
                logger.warning("Email provider credentials are missing or placeholders; recording as simulated")
                send_stub(channel, recipient, subject, body)
                return False
            _send_email(recipient, subject, body, config)
            return True
        elif channel == NotificationChannel.slack:
            config = _required_env("SLACK_WEBHOOK_URL")
            if config is None:
                logger.warning("Slack webhook is missing or a placeholder; recording as simulated")
                send_stub(channel, recipient, subject, body)
                return False
            _send_webhook("Slack", config["SLACK_WEBHOOK_URL"], body, subject)
            return True
        elif channel == NotificationChannel.teams:
            config = _required_env("TEAMS_WEBHOOK_URL")
            if config is None:
                logger.warning("Teams webhook is missing or a placeholder; recording as simulated")
                send_stub(channel, recipient, subject, body)
                return False
            _send_webhook("Teams", config["TEAMS_WEBHOOK_URL"], body, subject)
            return True
        elif channel == NotificationChannel.sms:
            config = _required_env("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER")
            if config is None:
                logger.warning("Twilio settings are missing or placeholders; recording as simulated")
                send_stub(channel, recipient, subject, body)
                return False
            _send_sms(recipient, body, config)
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
