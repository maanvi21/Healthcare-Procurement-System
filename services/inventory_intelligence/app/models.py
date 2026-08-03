import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class StockCategory(str, enum.Enum):
    drug = "drug"
    consumable = "consumable"
    ppe = "ppe"
    implant = "implant"
    equipment = "equipment"


class ReservationStatus(str, enum.Enum):
    reserved = "reserved"
    released = "released"
    fulfilled = "fulfilled"
    expired = "expired"


class StockItem(Base):
    __tablename__ = "stock_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    category: Mapped[StockCategory] = mapped_column(Enum(StockCategory, name="stock_category"))
    unit: Mapped[str] = mapped_column(String(32), default="unit")
    cold_chain: Mapped[bool] = mapped_column(Boolean, default=False)
    reorder_point: Mapped[int] = mapped_column(default=10)
    reorder_qty: Mapped[int] = mapped_column(default=50)

    batches: Mapped[list["StockBatch"]] = relationship(back_populates="stock_item", cascade="all, delete-orphan")


class StockBatch(Base):
    __tablename__ = "stock_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id"))
    batch_no: Mapped[str] = mapped_column(String(64))
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity_on_hand: Mapped[int] = mapped_column(default=0)
    warehouse_location: Mapped[str] = mapped_column(String(128), default="main-store")

    stock_item: Mapped["StockItem"] = relationship(back_populates="batches")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id"))
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_batches.id"))
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))  # cross-service ref -> approval_workflow.procurement_requests.id
    quantity: Mapped[int] = mapped_column()
    status: Mapped[ReservationStatus] = mapped_column(Enum(ReservationStatus, name="reservation_status"), default=ReservationStatus.reserved)
    reserved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Backorder(Base):
    __tablename__ = "backorders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id"))
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    quantity_short: Mapped[int] = mapped_column()
    suggested_reorder_qty: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
