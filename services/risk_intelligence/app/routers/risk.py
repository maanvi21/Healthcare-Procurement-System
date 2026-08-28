import uuid

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import analytics, anomaly
from app.db import get_db
from app.models import RiskAssessment, VendorObservation
from app.schemas import (
    RiskAssessmentOut,
    RiskAssessmentRequest,
    VendorObservationOut,
    VendorRiskProfileOut,
)
from app.service import assess_vendor

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/assess", response_model=RiskAssessmentOut)
def assess(payload: RiskAssessmentRequest, db: Session = Depends(get_db)):
    try:
        return assess_vendor(db, payload.vendor_id, payload.operational_signals())
    except requests.RequestException:
        raise HTTPException(502, "Could not reach vendor_intelligence to fetch vendor profile")


@router.get("/assessments", response_model=list[RiskAssessmentOut])
def list_assessments(vendor_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = (
        select(RiskAssessment)
        .options(selectinload(RiskAssessment.features))
        .order_by(RiskAssessment.assessed_at.desc())
    )
    if vendor_id:
        query = query.where(RiskAssessment.vendor_id == vendor_id)
    return db.execute(query).scalars().all()


@router.get("/anomalies", response_model=list[RiskAssessmentOut])
def list_anomalies(
    limit: int = Query(default=50, le=200),
    include_cold_start: bool = Query(
        default=False,
        description="Cold-start assessments are computed from little or no history; "
                    "excluded by default so the queue shows evidence-backed anomalies.",
    ),
    db: Session = Depends(get_db),
):
    """Vendors whose latest behaviour was flagged anomalous — the review queue."""
    query = (
        select(RiskAssessment)
        .options(selectinload(RiskAssessment.features))
        .where(RiskAssessment.anomaly_flag.is_(True))
        .order_by(RiskAssessment.anomaly_score.desc(), RiskAssessment.assessed_at.desc())
        .limit(limit)
    )
    if not include_cold_start:
        query = query.where(RiskAssessment.is_cold_start.is_(False))
    return db.execute(query).scalars().all()


@router.get("/assessments/{vendor_id}/latest", response_model=RiskAssessmentOut)
def latest_assessment(vendor_id: uuid.UUID, db: Session = Depends(get_db)):
    assessment = db.execute(
        select(RiskAssessment)
        .options(selectinload(RiskAssessment.features))
        .where(RiskAssessment.vendor_id == vendor_id)
        .order_by(RiskAssessment.assessed_at.desc())
    ).scalars().first()
    if not assessment:
        raise HTTPException(404, "No assessment found for this vendor")
    return assessment


@router.get("/vendors/{vendor_id}/profile", response_model=VendorRiskProfileOut)
def vendor_profile(vendor_id: uuid.UUID, db: Session = Depends(get_db)):
    """The measured evidence behind a vendor's score.

    Exists so a risk band is auditable: a reviewer can see the spend volatility, observed
    fraud rate and anomaly reasons that produced it, rather than being handed a number.
    """
    measured = analytics.profile(db, vendor_id)
    series = analytics.spend_series(db, vendor_id)
    peer_mean, peer_stdev = analytics.peer_amount_stats(db, exclude_vendor_id=vendor_id)
    detected = anomaly.detect(series, peer_mean, peer_stdev)

    return VendorRiskProfileOut(
        vendor_id=vendor_id,
        observation_count=measured["observation_count"],
        document_count=measured["document_count"],
        total_spend=measured["total_spend"],
        doc_fraud_flag_rate=measured["doc_fraud_flag_rate"],
        doc_mean_fraud_score=measured["doc_mean_fraud_score"],
        duplicate_invoice_rate=measured["duplicate_invoice_rate"],
        late_delivery_rate=measured["late_delivery_rate"],
        spend_volatility=measured["spend_volatility"],
        spend_growth_ratio=measured["spend_growth_ratio"],
        max_amount_zscore=measured["max_amount_zscore"],
        round_amount_rate=measured["round_amount_rate"],
        days_since_last_activity=measured["days_since_last_activity"],
        anomaly_score=detected["anomaly_score"],
        anomaly_flag=detected["anomaly_flag"],
        anomaly_reasons=detected["reasons"],
        is_cold_start=measured["observation_count"] < 3,
    )


@router.get("/vendors/{vendor_id}/observations", response_model=list[VendorObservationOut])
def vendor_observations(
    vendor_id: uuid.UUID, limit: int = Query(default=100, le=500), db: Session = Depends(get_db)
):
    """Raw behaviour history — the audit trail under every derived feature."""
    return db.execute(
        select(VendorObservation)
        .where(VendorObservation.vendor_id == vendor_id)
        .order_by(VendorObservation.occurred_at.desc())
        .limit(limit)
    ).scalars().all()
