import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import requests

from app.db import get_db
from app.schemas import RiskAssessmentOut, RiskAssessmentRequest
from app.service import assess_vendor
from app.models import RiskAssessment

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/assess", response_model=RiskAssessmentOut)
def assess(payload: RiskAssessmentRequest, db: Session = Depends(get_db)):
    signals = payload.model_dump(exclude={"vendor_id"})
    try:
        return assess_vendor(db, payload.vendor_id, signals)
    except requests.RequestException:
        raise HTTPException(502, "Could not reach vendor_intelligence to fetch vendor profile")


@router.get("/assessments", response_model=list[RiskAssessmentOut])
def list_assessments(vendor_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = select(RiskAssessment).order_by(RiskAssessment.assessed_at.desc())
    if vendor_id:
        query = query.where(RiskAssessment.vendor_id == vendor_id)
    return db.execute(query).scalars().all()


@router.get("/assessments/{vendor_id}/latest", response_model=RiskAssessmentOut)
def latest_assessment(vendor_id: uuid.UUID, db: Session = Depends(get_db)):
    assessment = db.execute(
        select(RiskAssessment).where(RiskAssessment.vendor_id == vendor_id).order_by(RiskAssessment.assessed_at.desc())
    ).scalars().first()
    if not assessment:
        raise HTTPException(404, "No assessment found for this vendor")
    return assessment
