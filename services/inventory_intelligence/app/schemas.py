import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models import ReservationStatus, StockCategory


class StockItemCreate(BaseModel):
    sku: str
    name: str
    category: StockCategory
    unit: str = "unit"
    cold_chain: bool = False
    reorder_point: int = 10
    reorder_qty: int = 50


class StockItemOut(StockItemCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True


class StockBatchCreate(BaseModel):
    batch_no: str
    expiry_date: date | None = None
    quantity_on_hand: int
    warehouse_location: str = "main-store"


class StockBatchOut(StockBatchCreate):
    id: uuid.UUID
    stock_item_id: uuid.UUID

    class Config:
        from_attributes = True


class ReservationRequest(BaseModel):
    stock_item_id: uuid.UUID
    quantity: int
    request_id: uuid.UUID


class ReservationOut(BaseModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    batch_id: uuid.UUID
    request_id: uuid.UUID
    quantity: int
    status: ReservationStatus
    reserved_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class ReservationResult(BaseModel):
    reservations: list[ReservationOut]
    reserved_quantity: int
    shortfall: int
    backorder_created: bool


class BackorderOut(BaseModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    request_id: uuid.UUID
    quantity_short: int
    suggested_reorder_qty: int
    created_at: datetime

    class Config:
        from_attributes = True
