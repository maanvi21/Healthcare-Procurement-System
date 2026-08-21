"""Vendor risk assessment: master data + measured behaviour + anomaly detection.

The assessment pipeline is:

1. Pull vendor master data from vendor_intelligence (licence, GSTIN, watchlist standing).
2. Derive behavioural features from the vendor's observation history (`app/analytics.py`).
3. Run unsupervised anomaly detection over their spend series (`app/anomaly.py`).
4. Score six risk dimensions with the registered MLflow model (`app/model.py`).
5. Persist the assessment with a snapshot of every feature that produced it, and publish
   `risk.assessed`.

Step 2 is what changed the meaning of the output. Previously five of eight features were
constants, so the "risk band" was effectively licence expiry wearing a model's clothes.
Assessments now carry `observation_count` and `is_cold_start`, so a consumer can tell
whether a band is backed by evidence — and `approval_workflow` feeds `vendor_risk_band`
into OPA routing, which is precisely where an unearned "low" would do damage.
"""
import json
import logging
from datetime import date, datetime

import requests
from sqlalchemy.orm import Session

from app import analytics, anomaly
from app.config import settings
from app.features import FEATURE_NAMES, build_feature_vector
from app.kafka_producer import publish_event
from app.mlflow_utils import get_or_train_model
from app.model import overall_risk_and_band, predict_risk
from app.models import RiskAssessment, RiskBand, RiskFeatureSnapshot

logger = logging.getLogger("risk_intelligence.service")

# a vendor needs at least this much history before an assessment counts as measured
_MIN_OBSERVATIONS_FOR_CONFIDENCE = 3


def _fetch_vendor(vendor_id) -> dict:
    response = requests.get(f"{settings.vendor_intelligence_url}/vendors/{vendor_id}", timeout=5)
    response.raise_for_status()
    return response.json()


def assess_vendor(db: Session, vendor_id, operational_signals: dict | None = None) -> RiskAssessment:
    operational_signals = operational_signals or {}
    vendor = _fetch_vendor(vendor_id)

    license_expiry = vendor.get("drug_license_expiry")
    if license_expiry:
        license_days_to_expiry = (datetime.strptime(license_expiry, "%Y-%m-%d").date() - date.today()).days
    else:
        license_days_to_expiry = 365  # not applicable to this vendor type — treat as non-issue

    gstin_valid = bool(vendor.get("gst_number"))
    watchlist_hit = "watchlist" in (vendor.get("review_reason") or "").lower()

    # --- measured behaviour ---
    measured = analytics.profile(db, vendor_id)

    # --- anomaly detection over the spend series ---
    series = analytics.spend_series(db, vendor_id)
    peer_mean, peer_stdev = analytics.peer_amount_stats(db, exclude_vendor_id=vendor_id)
    anomaly_result = anomaly.detect(series, peer_mean, peer_stdev)

    # Caller-supplied signals still win when provided — a WMS/ERP integration passing real
    # cold-chain or financial data should override the cold-start default, not be ignored.
    def signal(name):
        return operational_signals.get(name, measured[name])

    feature_vector = build_feature_vector(
        license_days_to_expiry=license_days_to_expiry,
        gstin_valid=gstin_valid,
        watchlist_hit=watchlist_hit,
        years_in_business=signal("years_in_business"),
        cold_chain_violation_count=signal("cold_chain_violation_count"),
        financial_health_score=signal("financial_health_score"),
        prior_compliance_flags=signal("prior_compliance_flags"),
        late_delivery_rate=signal("late_delivery_rate"),
        doc_fraud_flag_rate=measured["doc_fraud_flag_rate"],
        doc_mean_fraud_score=measured["doc_mean_fraud_score"],
        duplicate_invoice_rate=measured["duplicate_invoice_rate"],
        log_total_spend=analytics.log_scale(measured["total_spend"]),
        spend_volatility=measured["spend_volatility"],
        spend_growth_ratio=measured["spend_growth_ratio"],
        max_amount_zscore=measured["max_amount_zscore"],
        round_amount_rate=measured["round_amount_rate"],
        anomaly_score=anomaly_result["anomaly_score"],
    )

    model, version = get_or_train_model()
    scores = predict_risk(model, feature_vector)
    overall, band = overall_risk_and_band(scores, settings.risk_band_low_max, settings.risk_band_medium_max)

    observation_count = measured["observation_count"]
    is_cold_start = observation_count < _MIN_OBSERVATIONS_FOR_CONFIDENCE

    assessment = RiskAssessment(
        vendor_id=vendor_id,
        model_version=str(version),
        overall_risk=overall,
        risk_band=RiskBand(band),
        anomaly_score=anomaly_result["anomaly_score"],
        anomaly_flag=anomaly_result["anomaly_flag"],
        anomaly_reasons=json.dumps(anomaly_result["reasons"])[:1024] if anomaly_result["reasons"] else None,
        observation_count=observation_count,
        is_cold_start=is_cold_start,
        **scores,
    )
    db.add(assessment)
    db.flush()
    for name, value in zip(FEATURE_NAMES, feature_vector):
        db.add(RiskFeatureSnapshot(assessment_id=assessment.id, feature_name=name, feature_value=value))
    db.commit()
    db.refresh(assessment)

    publish_event("risk.assessed", str(vendor_id), {
        "vendor_id": str(vendor_id),
        "overall_risk": overall,
        "risk_band": band,
        "anomaly_flag": anomaly_result["anomaly_flag"],
        "anomaly_score": anomaly_result["anomaly_score"],
        "anomaly_reasons": anomaly_result["reasons"],
        "is_cold_start": is_cold_start,
        "observation_count": observation_count,
        "dimensions": scores,
    })
    if anomaly_result["anomaly_flag"]:
        logger.warning("Vendor %s flagged anomalous: %s", vendor_id, "; ".join(anomaly_result["reasons"]))
    return assessment
