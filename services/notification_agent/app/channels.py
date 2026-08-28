"""Multi-channel notification senders — demo/dev stubs only.

No third-party SDKs or credentials are required. Each channel logs the payload that
would have been delivered so the service is useful in local compose demos without
binding the project to Twilio / SendGrid / Teams / Slack accounts.
"""
import logging

from app.models import NotificationChannel

logger = logging.getLogger("notification_agent.channels")


def send_stub(channel: NotificationChannel, recipient: str, subject: str | None, body: str) -> None:
    logger.info(
        "[STUB %s] to=%s subject=%s body=%s",
        channel.value.upper(),
        recipient,
        subject or "(none)",
        body[:500] + ("…" if len(body) > 500 else ""),
    )
