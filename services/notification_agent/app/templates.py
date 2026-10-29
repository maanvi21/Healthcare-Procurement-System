"""Default notification templates (Jinja2). Seeded into notification_templates on
first startup so event-driven alerts have something to render against without
manual setup."""
from jinja2 import Environment

from app.models import NotificationChannel

_env = Environment(autoescape=False)


def render(body_template: str, context: dict) -> str:
    template = _env.from_string(body_template)
    return template.render(**context)


# One email template for every event currently published by the platform.
DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "Document uploaded (email)",
        "event_type": "documents.ingested",
        "channel": NotificationChannel.email,
        "subject_template": "Document uploaded: {{ filename | default(document_id) }}",
        "body_template": "Document {{ filename | default(document_id) }} was uploaded (source: {{ source | default('n/a') }}).",
    },
    {
        "name": "Document processed (email)",
        "event_type": "documents.processed",
        "channel": NotificationChannel.email,
        "subject_template": "Document processed: {{ document_id }}",
        "body_template": (
            "Document {{ document_id }} was processed (type: {{ doc_type | default('n/a') }}, "
            "status: {{ status | default('n/a') }}, fraud flag: {{ fraud_flag | default(false) }})."
        ),
    },
    {
        "name": "Document reviewed (email)",
        "event_type": "documents.reviewed",
        "channel": NotificationChannel.email,
        "subject_template": "Document review completed: {{ document_id }}",
        "body_template": "Document {{ document_id }} review is complete (type: {{ doc_type | default('n/a') }}, status: {{ status | default('n/a') }}).",
    },
    {
        "name": "Approval requested (email)",
        "event_type": "approval.requested",
        "channel": NotificationChannel.email,
        "recipient_template": "{{ approver_email }}",
        "subject_template": "Approval required: {{ request_title | default(request_id) }}",
        "body_template": "Request {{ request_id }} ({{ request_title | default('Procurement request') }}) requires review by {{ approver_role | default('approver') }}.",
    },
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
        "name": "Vendor updated (email)",
        "event_type": "vendor.updated",
        "channel": NotificationChannel.email,
        "subject_template": "Vendor record updated: {{ vendor_id }}",
        "body_template": "Vendor {{ vendor_id }} was updated. Changed fields: {{ changed_fields | default([]) }}.",
    },
    {
        "name": "Procurement request created (email)",
        "event_type": "procurement.request.created",
        "channel": NotificationChannel.email,
        "subject_template": "Procurement request created: {{ request_id }}",
        "body_template": "Procurement request {{ request_id }} was created for vendor {{ vendor_id | default('n/a') }} (total value: {{ total_value | default('n/a') }}).",
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
        "name": "Approval escalated (email)",
        "event_type": "approval.escalated",
        "channel": NotificationChannel.email,
        "subject_template": "Approval escalated: {{ request_id }}",
        # temporal_workflows.escalate_step publishes request_id + step_order (no vendor_id)
        "body_template": (
            "Approval {{ request_id }} was escalated at step {{ step_order | default('n/a') }} "
            "and needs attention."
        ),
    },
    {
        "name": "Inventory reserved (email)",
        "event_type": "inventory.reserved",
        "channel": NotificationChannel.email,
        "subject_template": "Inventory reserved for request {{ request_id }}",
        "body_template": "{{ quantity | default('Some') }} units were reserved for stock item {{ stock_item_id | default('n/a') }} (request {{ request_id | default('n/a') }}).",
    },
    {
        "name": "Risk assessed (email)",
        "event_type": "risk.assessed",
        "channel": NotificationChannel.email,
        "subject_template": "Vendor risk assessed: {{ vendor_id }} ({{ risk_band | default('n/a') }})",
        # field names must match risk_intelligence's published payload exactly
        # (service.py publishes overall_risk, not risk_score)
        "body_template": (
            "Risk for vendor {{ vendor_id }}: band={{ risk_band | default('n/a') }} "
            "score={{ overall_risk | default('n/a') }}"
        ),
    },
    {
        "name": "Inventory backorder (email)",
        "event_type": "inventory.backorder",
        "channel": NotificationChannel.email,
        # inventory_intelligence publishes stock_item_id / quantity_short (reservation.py)
        "subject_template": "Backorder alert: {{ stock_item_id | default('item') }}",
        "body_template": (
            "Inventory backorder for stock item {{ stock_item_id | default('n/a') }} "
            "(short by {{ quantity_short | default('n/a') }}, request={{ request_id | default('n/a') }})."
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
    {
        "name": "Contract generated (email)",
        "event_type": "contract.generated",
        "channel": NotificationChannel.email,
        "subject_template": "Contract generated: {{ contract_id }}",
        "body_template": "A contract was generated for vendor {{ vendor_id | default('n/a') }}. Contract ID: {{ contract_id }}.",
    },
    {
        "name": "Contract sent for signature (email)",
        "event_type": "contract.sent_for_signature",
        "channel": NotificationChannel.email,
        "recipient_template": "{{ signer_email }}",
        "subject_template": "Contract sent for signature: {{ contract_id }}",
        "body_template": "Contract {{ contract_id }} for vendor {{ vendor_id | default('n/a') }} has been sent for electronic signature.",
    },
]
