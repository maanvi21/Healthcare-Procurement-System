import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RiskBand(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    compliance_risk: Mapped[float] = mapped_column(Float)
    fraud_risk: Mapped[float] = mapped_column(Float)
    financial_risk: Mapped[float] = mapped_column(Float)
    supplier_risk: Mapped[float] = mapped_column(Float)
    operational_risk: Mapped[float] = mapped_column(Float)
    overall_risk: Mapped[float] = mapped_column(Float)
    risk_band: Mapped[RiskBand] = mapped_column(Enum(RiskBand, name="risk_band"))
    model_version: Mapped[str] = mapped_column(String(64))
    assessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    features: Mapped[list["RiskFeatureSnapshot"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")


class RiskFeatureSnapshot(Base):
    __tablename__ = "risk_features_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("risk_assessments.id"))
    feature_name: Mapped[str] = mapped_column(String(128))
    feature_value: Mapped[float] = mapped_column(Float)

    assessment: Mapped["RiskAssessment"] = relationship(back_populates="features")
