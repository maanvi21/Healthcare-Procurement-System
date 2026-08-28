"""Default notification templates (Jinja2). Seeded into notification_templates on
first startup so event-driven alerts have something to render against without
manual setup."""
from jinja2 import Environment

from app.models import NotificationChannel

_env = Environment(autoescape=False)


def render(body_template: str, context: dict) -> str:
    template = _env.from_string(body_template)
    return template.render(**context)


# Each entry: (name, event_type, channel, subject_template, body_template)
DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "Vendor onboarded (email)",
        "event_type": "vendor.onboarded",
        "channel": NotificationChannel.email,
        "subject_template": "Vendor onboarded: {{ vendor_id }}",
        "body_template": (
            "Vendor {{ vendor_id }} was onboarded with status {{ status | default('pending_review') }} "
            "(type: {{ vendor_type | default('n/a') }})."
        ),
    },
    {
        "name": "Document processed (Slack)",
        "event_type": "documents.processed",
        "channel": NotificationChannel.slack,
        "subject_template": None,
        "body_template": (
            "*Document processed*\n"
            "document_id={{ document_id | default('n/a') }} "
            "vendor_id={{ vendor_id | default('n/a') }} "
            "doc_type={{ doc_type | default('n/a') }}"
        ),
    },
    {
        "name": "Approval approved (email)",
        "event_type": "approval.approved",
        "channel": NotificationChannel.email,
        "subject_template": "Approval approved: {{ request_id }}",
        "body_template": (
            "Procurement request {{ request_id }} for vendor {{ vendor_id | default('n/a') }} was approved."
        ),
    },
    {
        "name": "Approval rejected (email)",
        "event_type": "approval.rejected",
        "channel": NotificationChannel.email,
        "subject_template": "Approval rejected: {{ request_id }}",
        "body_template": (
            "Procurement request {{ request_id }} for vendor {{ vendor_id | default('n/a') }} was rejected."
        ),
    },
    {
        "name": "Approval escalated (Teams)",
        "event_type": "approval.escalated",
        "channel": NotificationChannel.teams,
        "subject_template": "Approval escalated: {{ request_id }}",
        "body_template": (
            "Approval {{ request_id }} for vendor {{ vendor_id | default('n/a') }} was escalated and needs attention."
        ),
    },
    {
        "name": "Risk assessed (SMS)",
        "event_type": "risk.assessed",
        "channel": NotificationChannel.sms,
        "subject_template": None,
        "body_template": (
            "Risk for vendor {{ vendor_id }}: band={{ risk_band | default('n/a') }} "
            "score={{ risk_score | default('n/a') }}"
        ),
    },
    {
        "name": "Inventory backorder (email)",
        "event_type": "inventory.backorder",
        "channel": NotificationChannel.email,
        "subject_template": "Backorder alert: {{ sku | default('item') }}",
        "body_template": (
            "Inventory backorder for {{ sku or item_id or 'n/a' }} "
            "(qty={{ quantity | default('n/a') }}, request={{ request_id | default('n/a') }})."
        ),
    },
    {
        "name": "Contract signed (email)",
        "event_type": "contract.signed",
        "channel": NotificationChannel.email,
        "subject_template": "Contract signed: {{ contract_id | default('n/a') }}",
        "body_template": (
            "Contract {{ contract_id | default('n/a') }} for vendor {{ vendor_id | default('n/a') }} was signed."
        ),
    },
]
