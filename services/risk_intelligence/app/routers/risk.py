import uuid

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import analytics, anomaly
from app.auth import require_roles
from app.db import get_db
from app.features import FEATURE_NAMES
from app.mlflow_utils import get_or_train_model
from app.models import RiskAssessment, VendorObservation
from app.schemas import (
    RiskAssessmentOut,
    RiskAssessmentRequest,
    VendorObservationOut,
    VendorRiskProfileOut,
)
from app.service import assess_vendor
from app.shap_explain import explain_prediction

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/assess", response_model=RiskAssessmentOut)
def assess(
    payload: RiskAssessmentRequest,
    db: Session = Depends(get_db),
    _role: str = Depends(require_roles(["finance_manager", "compliance_officer", "procurement_director"])),
):
    try:
        return assess_vendor(db, payload.vendor_id, payload.operational_signals())
    except requests.RequestException:
        raise HTTPException(502, "Could not reach vendor_intelligence to fetch vendor profile")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


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
    """Vendors whose latest behaviour was flagged anomalous — the review queue.

    One row per vendor, not one per flagged assessment. Returning every historical
    flagged row made the queue misleading in both directions: a vendor re-assessed six
    times appeared six times (so "18 flagged" was really 3 vendors), and a vendor whose
    problem had since cleared stayed in the queue forever behind an old flagged row.
    Take each vendor's most recent assessment first, then keep it only if *that* one is
    flagged — which is what "latest behaviour was flagged" means.
    """
    latest = (
        select(
            RiskAssessment.id,
            func.row_number()
            .over(partition_by=RiskAssessment.vendor_id, order_by=RiskAssessment.assessed_at.desc())
            .label("rn"),
        )
        .subquery()
    )
    query = (
        select(RiskAssessment)
        .join(latest, latest.c.id == RiskAssessment.id)
        .options(selectinload(RiskAssessment.features))
        .where(latest.c.rn == 1)
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


@router.get("/vendors/{vendor_id}/explain")
def explain_vendor_risk(vendor_id: uuid.UUID, top_n: int = Query(default=5, ge=1, le=17), db: Session = Depends(get_db)):
    """SHAP attribution for this vendor's most recent assessment.

    Replays the exact feature vector that produced the stored scores (persisted as
    RiskFeatureSnapshot rows at assessment time) through the registered model, so the
    explanation belongs to the score the platform actually published — not to a fresh
    prediction that might differ if the vendor's data has moved since.
    """
    assessment = db.execute(
        select(RiskAssessment)
        .options(selectinload(RiskAssessment.features))
        .where(RiskAssessment.vendor_id == vendor_id)
        .order_by(RiskAssessment.assessed_at.desc())
    ).scalars().first()
    if not assessment:
        raise HTTPException(404, "No assessment found for this vendor — run one first")

    snapshot = {f.feature_name: f.feature_value for f in assessment.features}
    if not snapshot:
        raise HTTPException(
            409,
            "This assessment predates feature snapshots, so it cannot be explained — re-assess the vendor",
        )

    feature_vector = [snapshot.get(name, 0.0) for name in FEATURE_NAMES]
    try:
        model, version = get_or_train_model()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    attribution = explain_prediction(model, str(version), feature_vector, top_n=top_n)

    if not attribution:
        raise HTTPException(503, "SHAP attribution unavailable (shap library not installed)")

    policy_adjustments = []
    if snapshot.get("gstin_valid", 1.0) < 0.5:
        policy_adjustments.append(
            "Missing or malformed GSTIN: compliance risk is subject to a 0.80 minimum, "
            "so the final risk band can be higher than the raw model attribution."
        )

    return {
        "vendor_id": str(vendor_id),
        "assessment_id": str(assessment.id),
        "assessed_at": assessment.assessed_at,
        "model_version": assessment.model_version,
        "risk_band": assessment.risk_band.value,
        "overall_risk": assessment.overall_risk,
        "is_cold_start": assessment.is_cold_start,
        "observation_count": assessment.observation_count,
        "method": "TreeExplainer (exact Shapley values over the gradient-boosted trees)",
        "dimensions": attribution,
        "policy_adjustments": policy_adjustments,
    }


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
