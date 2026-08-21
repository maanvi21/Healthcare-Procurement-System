"""Procurement-request creation, shared by the HTTP router and the Kafka consumer.

Both entry points must produce an identical request: the same OPA-evaluated approver
chain, the same Temporal workflow, the same `procurement.request.created` event. Keeping
that in one place is what stops the document-driven path from drifting away from the
UI-driven one.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.kafka_producer import publish_event
from app.models import ApprovalHistory, ApprovalStep, ProcurementRequest, StepStatus
from app.opa_client import get_approval_steps
from app.schemas import ProcurementRequestCreate
from app.temporal_client import get_client
from app.temporal_workflows import ApprovalWorkflow

logger = logging.getLogger(__name__)


async def create_procurement_request(
    payload: ProcurementRequestCreate, source_document_id: str | None = None
) -> str:
    """Creates the request + approval steps, starts the Temporal workflow, emits the event.

    Returns the new request id. `source_document_id` links the request back to the
    document that triggered it (null for requests raised by hand in the UI).
    """
    steps_plan = get_approval_steps(
        payload.department, payload.category, payload.total_value, payload.vendor_risk_band
    )

    db: Session = SessionLocal()
    try:
        request = ProcurementRequest(
            requested_by=payload.requested_by, department=payload.department,
            category=payload.category, vendor_id=payload.vendor_id, items=payload.items,
            total_value=payload.total_value, currency=payload.currency,
            source_document_id=source_document_id,
        )
        db.add(request)
        db.flush()

        for idx, step in enumerate(steps_plan):
            db.add(ApprovalStep(
                request_id=request.id, step_order=idx, approver_role=step["approver_role"],
                status=StepStatus.pending, sla_hours=step["sla_hours"],
                sla_deadline=datetime.utcnow() + timedelta(hours=step["sla_hours"]),
            ))
        db.add(ApprovalHistory(request_id=request.id, event="request_created", actor=payload.requested_by))

        workflow_id = f"approval-{request.id}"
        request.workflow_id = workflow_id
        db.commit()
        db.refresh(request)
        request_id = str(request.id)
    finally:
        db.close()

    # The request is already durable in Postgres at this point. If Temporal is down the
    # SLA/escalation timer won't run, but the request itself must not be lost — an
    # approver can still act on it through the API.
    try:
        client = await get_client()
        await client.start_workflow(
            ApprovalWorkflow.run,
            args=[request_id, [{"step_order": i, **s} for i, s in enumerate(steps_plan)]],
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except Exception:
        logger.exception("Temporal workflow start failed for request %s — SLA tracking inactive", request_id)

    publish_event("procurement.request.created", request_id, {
        "request_id": request_id,
        "vendor_id": str(payload.vendor_id) if payload.vendor_id else None,
        "items": payload.items,
        "total_value": payload.total_value,
        "source_document_id": source_document_id,
    })
    return request_id
