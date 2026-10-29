import json
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

from app.explain import explain_scores
from app.models import ObservationSource, RiskBand


class RiskAssessmentRequest(BaseModel):
    """Manually trigger an assessment.

    Every operational signal is optional and defaults to `None`, meaning "use what the
    platform measured". Supplying one overrides the measurement for that field — which is
    how a WMS/ERP integration feeds in cold-chain or financial data the platform cannot
    observe for itself. These used to default to fixed numbers, which silently overrode
    real measurements with assumptions on every call.
    """
    vendor_id: uuid.UUID
    cold_chain_violation_count: int | None = None
    late_delivery_rate: float | None = None
    financial_health_score: float | None = None
    prior_compliance_flags: int | None = None
    years_in_business: float | None = None

    def operational_signals(self) -> dict:
        """Only the signals the caller actually supplied."""
        return {
            k: v for k, v in self.model_dump(exclude={"vendor_id"}).items() if v is not None
        }


class RiskAssessmentOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    compliance_risk: float
    fraud_risk: float
    financial_risk: float
    supplier_risk: float
    spend_risk: float
    operational_risk: float
    overall_risk: float
    risk_band: RiskBand
    anomaly_score: float
    anomaly_flag: bool
    anomaly_reasons: list[str] = []
    observation_count: int
    is_cold_start: bool
    model_version: str
    model_status: str = "unvalidated"
    assessed_at: datetime
    # plain-language reasons per dimension, e.g. {"compliance_risk": ["Drug licence is
    # already expired (12 days overdue)."]} -- see app/explain.py. Empty for assessments
    # created before this field existed (no feature snapshot to explain from).
    explanations: dict[str, list[str]] = {}

    # `from_attributes` to read ORM rows; `protected_namespaces` opted out because
    # `model_version` collides with pydantic's reserved "model_" prefix and the field name
    # is part of the public API, so opting out beats renaming it.
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    @field_validator("anomaly_reasons", mode="before")
    @classmethod
    def _parse_reasons(cls, value):
        """Stored as a JSON string on the row; exposed as a list."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return value or []

    @model_validator(mode="before")
    @classmethod
    def _build_explanations(cls, obj):
        """Derives `explanations` from the assessment's persisted feature snapshot.

        `obj` is the ORM RiskAssessment row on the way out of the API (or a plain dict on
        a round-trip, e.g. re-validating an already-serialized response) -- only compute
        against the ORM row, where `.features` is the relationship to RiskFeatureSnapshot.
        """
        if isinstance(obj, dict):
            data = dict(obj)
            version = str(data.get("model_version", ""))
            data["model_status"] = "validated" if version.startswith("observed:") else (
                "synthetic_project" if version.startswith("synthetic:") else "unvalidated"
            )
            return data
        features = {snap.feature_name: snap.feature_value for snap in obj.features}
        # __dict__ carries every mapped column already; add the derived field on top
        data = dict(obj.__dict__)
        version = str(data.get("model_version", ""))
        data["model_status"] = "validated" if version.startswith("observed:") else (
            "synthetic_project" if version.startswith("synthetic:") else "unvalidated"
        )
        data["explanations"] = explain_scores(features)
        return data


class VendorObservationOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    source: ObservationSource
    source_id: str
    occurred_at: datetime
    doc_type: str | None
    amount: float | None
    reference_number: str | None
    fraud_flag: bool
    fraud_score: float
    is_duplicate: bool

    class Config:
        from_attributes = True


class VendorRiskProfileOut(BaseModel):
    """The measured evidence behind a vendor's risk score."""
    vendor_id: uuid.UUID
    observation_count: int
    document_count: int
    total_spend: float
    doc_fraud_flag_rate: float
    doc_mean_fraud_score: float
    duplicate_invoice_rate: float
    late_delivery_rate: float
    spend_volatility: float
    spend_growth_ratio: float
    max_amount_zscore: float
    round_amount_rate: float
    days_since_last_activity: float
    anomaly_score: float
    anomaly_flag: bool
    anomaly_reasons: list[str] = []
    is_cold_start: bool
