import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal, get_db
from app.models import ApprovalStep, ProcurementRequest, RequestStatus, StepStatus
from app.redis_client import is_duplicate_submission
from app.schemas import DecisionIn, ProcurementRequestCreate, ProcurementRequestOut
from app.service import create_procurement_request
from app.temporal_client import get_client
from app.temporal_workflows import ApprovalWorkflow

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/requests", response_model=ProcurementRequestOut)
async def create_request(payload: ProcurementRequestCreate):
    if is_duplicate_submission(payload.department, str(payload.vendor_id) if payload.vendor_id else None, payload.total_value, payload.items):
        raise HTTPException(409, "Duplicate submission detected — an identical request was just submitted")

    request_id = await create_procurement_request(payload)

    db = SessionLocal()
    try:
        # `steps` and `history` are lazy relationships, and this session is closed before
        # FastAPI serializes the response — so returning the ORM object directly raises
        # DetachedInstanceError while building the response body. Eager-load them and
        # convert to the response model while the session is still open.
        request = db.execute(
            select(ProcurementRequest)
            .options(
                selectinload(ProcurementRequest.steps),
                selectinload(ProcurementRequest.history),
            )
            .where(ProcurementRequest.id == request_id)
        ).scalars().first()
        if request is None:
            raise HTTPException(500, "Request was created but could not be read back")
        return ProcurementRequestOut.model_validate(request)
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


def current_step(request: ProcurementRequest) -> ApprovalStep | None:
    """The one step a request is actually waiting on.

    Approval is a sequential chain, but every step row is created with status `pending`,
    so "pending" alone cannot distinguish "your turn" from "queued behind two other
    approvers". The step in play is the lowest-ordered one still pending.
    """
    pending = [s for s in sorted(request.steps, key=lambda s: s.step_order)
               if s.status == StepStatus.pending]
    return pending[0] if pending else None


@router.get("/inbox", response_model=list[ProcurementRequestOut])
def approver_inbox(approver_role: str, db: Session = Depends(get_db)):
    """Requests genuinely awaiting this role — not every request that will eventually.

    Filtering on `status == pending` alone put a three-step pharma request in the
    department manager's, finance manager's *and* compliance officer's inbox at once, from
    the moment it was raised. Approving from the wrong one appeared to do nothing, because
    the workflow only accepts a decision for the step it is currently awaiting and
    discarded the rest.
    """
    candidates = db.execute(
        select(ProcurementRequest)
        .join(ApprovalStep)
        .where(ApprovalStep.approver_role == approver_role, ApprovalStep.status == StepStatus.pending)
        .order_by(ProcurementRequest.created_at)
    ).scalars().unique().all()

    return [r for r in candidates
            if (step := current_step(r)) is not None and step.approver_role == approver_role]


@router.post("/requests/{request_id}/decide")
async def decide(request_id: uuid.UUID, payload: DecisionIn):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")

    db = SessionLocal()
    try:
        request = db.get(ProcurementRequest, request_id)
        if not request:
            raise HTTPException(404, "Request not found")
        if request.status != RequestStatus.pending:
            raise HTTPException(409, f"This request is already {request.status.value}")

        # The workflow only accepts a decision for the step it is currently awaiting and
        # silently drops anything else. Returning 200 for a signal that will be discarded
        # is the worst possible answer: the caller is told it worked and nothing happens.
        # Refuse out-of-turn decisions here, naming who the request is actually waiting on.
        step = current_step(request)
        if step is None:
            raise HTTPException(409, "This request has no step awaiting a decision")
        if step.step_order != payload.step_order:
            raise HTTPException(
                409,
                f"This request is awaiting step {step.step_order + 1} "
                f"({step.approver_role.replace('_', ' ')}), not step {payload.step_order + 1}",
            )
        workflow_id = request.workflow_id
    finally:
        db.close()

    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(ApprovalWorkflow.decide, args=[payload.step_order, payload.decision, payload.actor, payload.note])
    return {"signalled": True}
