import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import RiskBand


class RiskAssessmentRequest(BaseModel):
    vendor_id: uuid.UUID
    cold_chain_violation_count: int = 0
    late_delivery_rate: float = 0.05
    financial_health_score: float = 0.7
    prior_compliance_flags: int = 0
    years_in_business: float = 3.0


class RiskAssessmentOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    compliance_risk: float
    fraud_risk: float
    financial_risk: float
    supplier_risk: float
    operational_risk: float
    overall_risk: float
    risk_band: RiskBand
    model_version: str
    assessed_at: datetime

    class Config:
        from_attributes = True
