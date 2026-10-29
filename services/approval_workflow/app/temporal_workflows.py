"""Temporal workflow + activities for procurement-request approval.

The workflow (`ApprovalWorkflow`) is the durable state machine: it walks the approver
chain OPA produced, waits for a `decide` signal within each step's SLA, and escalates to
the next step automatically on timeout. All I/O (Postgres writes, Kafka publishes) lives
in activities — the workflow function itself only orchestrates, per Temporal's
determinism requirements.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from app.db import SessionLocal
    from app.kafka_producer import publish_event
    from app.models import ApprovalHistory, ApprovalStep, ProcurementRequest, RequestStatus, StepStatus

APPROVER_EMAIL_DEFAULTS = {
    "department_manager": "dr.sarah@medisource.ai",
    "finance_manager": "mark.finance@medisource.ai",
    "compliance_officer": "elena.compliance@medisource.ai",
    "procurement_director": "arthur.procurement@medisource.ai",
}
USER_EMAIL_DEFAULTS = {
    "Dr. Sarah": "dr.sarah@medisource.ai",
    "Mark": "mark.finance@medisource.ai",
    "Elena": "elena.compliance@medisource.ai",
    "Arthur": "arthur.procurement@medisource.ai",
}


@dataclass
class StepInput:
    approver_role: str
    sla_hours: float


# ------------------------------------------------------------------------- activities
@activity.defn
async def mark_step_pending(request_id: str, step_order: int) -> None:
    db = SessionLocal()
    try:
        step = db.query(ApprovalStep).filter_by(request_id=request_id, step_order=step_order).one()
        step.status = StepStatus.pending
        request = db.get(ProcurementRequest, request_id)
        approver_email = ""
        try:
            approver_email = json.loads(os.getenv("APPROVER_EMAILS") or json.dumps(APPROVER_EMAIL_DEFAULTS)).get(step.approver_role, "")
        except (TypeError, json.JSONDecodeError):
            pass
        db.add(ApprovalHistory(request_id=request_id, event=f"step_{step_order}_started", actor="system"))
        db.commit()
        event_data = {
            "request_id": request_id,
            "step_order": step_order,
            "approver_role": step.approver_role,
            "approver_email": approver_email,
            "request_title": request.title if request else None,
            "vendor_id": str(request.vendor_id) if request and request.vendor_id else None,
        }
    finally:
        db.close()
    publish_event("approval.requested", request_id, event_data)


@activity.defn
async def record_decision(request_id: str, step_order: int, decision: str, actor: str, note: str | None) -> None:
    db = SessionLocal()
    try:
        step = db.query(ApprovalStep).filter_by(request_id=request_id, step_order=step_order).one()
        step.status = StepStatus.approved if decision == "approved" else StepStatus.rejected
        step.decided_at = datetime.utcnow()
        step.decision_note = note
        step.approver_id = actor
        db.add(ApprovalHistory(request_id=request_id, event=f"step_{step_order}_{decision}", actor=actor))
        db.commit()
    finally:
        db.close()


@activity.defn
async def escalate_step(request_id: str, step_order: int) -> None:
    db = SessionLocal()
    try:
        step = db.query(ApprovalStep).filter_by(request_id=request_id, step_order=step_order).one()
        step.status = StepStatus.escalated
        db.add(ApprovalHistory(request_id=request_id, event=f"step_{step_order}_escalated", actor="system"))
        db.commit()
    finally:
        db.close()
    publish_event("approval.escalated", request_id, {"request_id": request_id, "step_order": step_order})


@activity.defn
async def finalize_request(request_id: str, outcome: str) -> None:
    db = SessionLocal()
    try:
        request = db.get(ProcurementRequest, request_id)
        request.status = RequestStatus.approved if outcome == "approved" else RequestStatus.rejected
        db.add(ApprovalHistory(request_id=request_id, event=f"request_{outcome}", actor="system"))
        requester_email = request.requested_by if request and "@" in request.requested_by else None
        if request and not requester_email:
            try:
                requester_email = json.loads(os.getenv("USER_EMAILS") or json.dumps(USER_EMAIL_DEFAULTS)).get(request.requested_by)
            except (TypeError, json.JSONDecodeError):
                requester_email = None
        request_title = request.title if request else None
        db.commit()
        vendor_id = str(request.vendor_id) if request.vendor_id else None
    finally:
        db.close()
    topic = "approval.approved" if outcome == "approved" else "approval.rejected"
    publish_event(topic, request_id, {
        "request_id": request_id, "vendor_id": vendor_id,
        "requester_email": requester_email,
        "request_title": request_title,
    })


# --------------------------------------------------------------------------- workflow
@workflow.defn
class ApprovalWorkflow:
    def __init__(self) -> None:
        self._decision: str | None = None
        self._decision_actor: str | None = None
        self._decision_note: str | None = None
        self._awaited_step_order: int | None = None

    @workflow.signal
    def decide(self, step_order: int, decision: str, actor: str, note: str | None = None) -> None:
        if step_order != self._awaited_step_order:
            return  # stale/out-of-order signal for a step we've already moved past
        self._decision = decision
        self._decision_actor = actor
        self._decision_note = note

    @workflow.run
    async def run(self, request_id: str, steps: list[dict]) -> str:
        for step in steps:
            step_order = step["step_order"]
            sla_hours = step["sla_hours"]
            self._awaited_step_order = step_order
            self._decision = None

            await workflow.execute_activity(
                mark_step_pending, args=[request_id, step_order], start_to_close_timeout=timedelta(seconds=30),
            )

            try:
                await workflow.wait_condition(
                    lambda: self._decision is not None, timeout=timedelta(hours=sla_hours),
                )
            except TimeoutError:
                await workflow.execute_activity(
                    escalate_step, args=[request_id, step_order], start_to_close_timeout=timedelta(seconds=30),
                )
                continue  # move to next approver in the chain

            await workflow.execute_activity(
                record_decision,
                args=[request_id, step_order, self._decision, self._decision_actor, self._decision_note],
                start_to_close_timeout=timedelta(seconds=30),
            )

            if self._decision == "rejected":
                await workflow.execute_activity(
                    finalize_request, args=[request_id, "rejected"], start_to_close_timeout=timedelta(seconds=30),
                )
                return "rejected"

        await workflow.execute_activity(
            finalize_request, args=[request_id, "approved"], start_to_close_timeout=timedelta(seconds=30),
        )
        return "approved"
