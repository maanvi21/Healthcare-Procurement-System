from datetime import date, datetime

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.features import FEATURE_NAMES, build_feature_vector
from app.kafka_producer import publish_event
from app.mlflow_utils import get_or_train_model
from app.model import overall_risk_and_band, predict_risk
from app.models import RiskAssessment, RiskBand, RiskFeatureSnapshot


def _fetch_vendor(vendor_id) -> dict:
    response = requests.get(f"{settings.vendor_intelligence_url}/vendors/{vendor_id}", timeout=5)
    response.raise_for_status()
    return response.json()


def assess_vendor(db: Session, vendor_id, operational_signals: dict) -> RiskAssessment:
    vendor = _fetch_vendor(vendor_id)

    license_expiry = vendor.get("drug_license_expiry")
    if license_expiry:
        license_days_to_expiry = (datetime.strptime(license_expiry, "%Y-%m-%d").date() - date.today()).days
    else:
        license_days_to_expiry = 365  # not applicable to this vendor type — treat as non-issue

    gstin_valid = bool(vendor.get("gst_number"))
    watchlist_hit = "watchlist" in (vendor.get("review_reason") or "").lower()

    feature_vector = build_feature_vector(
        license_days_to_expiry=license_days_to_expiry,
        cold_chain_violation_count=operational_signals.get("cold_chain_violation_count", 0),
        late_delivery_rate=operational_signals.get("late_delivery_rate", 0.05),
        financial_health_score=operational_signals.get("financial_health_score", 0.7),
        prior_compliance_flags=operational_signals.get("prior_compliance_flags", 0),
        years_in_business=operational_signals.get("years_in_business", 3.0),
        gstin_valid=gstin_valid,
        watchlist_hit=watchlist_hit,
    )

    model, version = get_or_train_model()
    scores = predict_risk(model, feature_vector)
    overall, band = overall_risk_and_band(scores, settings.risk_band_low_max, settings.risk_band_medium_max)

    assessment = RiskAssessment(
        vendor_id=vendor_id, model_version=str(version), overall_risk=overall, risk_band=RiskBand(band), **scores,
    )
    db.add(assessment)
    db.flush()
    for name, value in zip(FEATURE_NAMES, feature_vector):
        db.add(RiskFeatureSnapshot(assessment_id=assessment.id, feature_name=name, feature_value=value))
    db.commit()
    db.refresh(assessment)

    publish_event("risk.assessed", str(vendor_id), {
        "vendor_id": str(vendor_id), "overall_risk": overall, "risk_band": band,
    })
    return assessment
