import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RiskBand(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ObservationSource(str, enum.Enum):
    """Which upstream event produced an observation — kept so a vendor's history can be
    audited back to the exact event, and so analytics can weight document-derived signals
    differently from approval-derived ones."""
    document = "document"
    procurement_request = "procurement_request"
    approval = "approval"


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    compliance_risk: Mapped[float] = mapped_column(Float)
    fraud_risk: Mapped[float] = mapped_column(Float)
    financial_risk: Mapped[float] = mapped_column(Float)
    supplier_risk: Mapped[float] = mapped_column(Float)
    operational_risk: Mapped[float] = mapped_column(Float)
    # spend risk — concentration, volatility and growth in what this vendor bills
    spend_risk: Mapped[float] = mapped_column(Float, default=0.0)
    overall_risk: Mapped[float] = mapped_column(Float)
    risk_band: Mapped[RiskBand] = mapped_column(Enum(RiskBand, name="risk_band"))
    # unsupervised anomaly score (see app/anomaly.py): how unlike this vendor's own
    # history, and unlike its peers, the current behaviour looks. Independent of the
    # supervised risk dimensions above, so a novel pattern is caught even when every
    # individual risk score looks unremarkable.
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_reasons: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # how much real history backed this assessment — an assessment computed from an empty
    # observation history is a cold-start estimate, not a measurement, and callers need to
    # be able to tell the difference
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    is_cold_start: Mapped[bool] = mapped_column(Boolean, default=True)
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


class VendorObservation(Base):
    """One recorded behaviour of a vendor, derived from a platform event.

    This is the analytics substrate the risk model was missing. Before it existed, five of
    the eight features were hardcoded constants, so every "risk band" was really a
    restatement of licence expiry. Observations accumulate from documents (invoices,
    delivery notes and their fraud screen results) and from procurement/approval activity,
    giving spend, fraud and supplier signals something real to measure.

    Rows are append-only and idempotent per (source, source_id) so Kafka redelivery cannot
    inflate a vendor's history — which would otherwise directly distort their risk score.
    """
    __tablename__ = "vendor_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source: Mapped[ObservationSource] = mapped_column(Enum(ObservationSource, name="observation_source"))
    # the upstream entity id (document_id / request_id) — unique per source
    source_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    doc_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # signals carried over from document_intelligence's own fraud screen
    fraud_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    fraud_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_vendor_observations_source_unique", "source", "source_id", unique=True),
        Index("ix_vendor_observations_vendor_time", "vendor_id", "occurred_at"),
    )
