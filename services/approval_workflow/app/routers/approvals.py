import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.kafka_producer import publish_event
from app.models import ApprovalHistory, ApprovalStep, ProcurementRequest, StepStatus
from app.opa_client import get_approval_steps
from app.redis_client import is_duplicate_submission
from app.schemas import DecisionIn, ProcurementRequestCreate, ProcurementRequestOut
from app.temporal_client import get_client
from app.temporal_workflows import ApprovalWorkflow

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/requests", response_model=ProcurementRequestOut)
async def create_request(payload: ProcurementRequestCreate):
    if is_duplicate_submission(payload.department, str(payload.vendor_id) if payload.vendor_id else None, payload.total_value, payload.items):
        raise HTTPException(409, "Duplicate submission detected — an identical request was just submitted")

    steps_plan = get_approval_steps(payload.department, payload.category, payload.total_value, payload.vendor_risk_band)

    db: Session = SessionLocal()
    try:
        request = ProcurementRequest(
            requested_by=payload.requested_by, department=payload.department, category=payload.category,
            vendor_id=payload.vendor_id, items=payload.items, total_value=payload.total_value, currency=payload.currency,
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

    client = await get_client()
    await client.start_workflow(
        ApprovalWorkflow.run,
        args=[request_id, [{"step_order": i, **s} for i, s in enumerate(steps_plan)]],
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    publish_event("procurement.request.created", request_id, {
        "request_id": request_id, "vendor_id": str(payload.vendor_id) if payload.vendor_id else None,
        "items": payload.items, "total_value": payload.total_value,
    })

    db = SessionLocal()
    try:
        return db.get(ProcurementRequest, request_id)
    finally:
        db.close()


@router.get("/requests", response_model=list[ProcurementRequestOut])
def list_requests(db: Session = Depends(get_db)):
    return db.execute(select(ProcurementRequest).order_by(ProcurementRequest.created_at.desc())).scalars().all()


@router.get("/requests/{request_id}", response_model=ProcurementRequestOut)
def get_request(request_id: uuid.UUID, db: Session = Depends(get_db)):
    request = db.get(ProcurementRequest, request_id)
    if not request:
        raise HTTPException(404, "Request not found")
    return request


@router.get("/inbox", response_model=list[ProcurementRequestOut])
def approver_inbox(approver_role: str, db: Session = Depends(get_db)):
    query = (
        select(ProcurementRequest)
        .join(ApprovalStep)
        .where(ApprovalStep.approver_role == approver_role, ApprovalStep.status == StepStatus.pending)
        .order_by(ProcurementRequest.created_at)
    )
    return db.execute(query).scalars().unique().all()


@router.post("/requests/{request_id}/decide")
async def decide(request_id: uuid.UUID, payload: DecisionIn):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")

    db = SessionLocal()
    try:
        request = db.get(ProcurementRequest, request_id)
        if not request:
            raise HTTPException(404, "Request not found")
        workflow_id = request.workflow_id
    finally:
        db.close()

    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(ApprovalWorkflow.decide, args=[payload.step_order, payload.decision, payload.actor, payload.note])
    return {"signalled": True}
