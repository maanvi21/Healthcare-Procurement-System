"""Kafka topics that the notification agent turns into email alerts."""

TOPICS = [
    "documents.ingested",
    "documents.processed",
    "documents.reviewed",
    "vendor.onboarded",
    "vendor.updated",
    "procurement.request.created",
    "approval.requested",
    "approval.approved",
    "approval.rejected",
    "approval.escalated",
    "risk.assessed",
    "inventory.reserved",
    "inventory.backorder",
    "contract.generated",
    "contract.sent_for_signature",
    "contract.signed",
]

# Subscribe to all business event namespaces, including new event topics added later.
TOPIC_PATTERN = r"^(documents|vendor|procurement|approval|risk|inventory|contract)\..+$"
