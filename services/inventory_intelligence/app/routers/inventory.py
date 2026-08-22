import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Backorder, Reservation, StockBatch, StockItem
from app.reservation import reserve_stock, sweep_expired_reservations
from app.schemas import (
    BackorderOut,
    ReservationOut,
    ReservationRequest,
    ReservationResult,
    StockBatchCreate,
    StockBatchOut,
    StockItemCreate,
    StockItemOut,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/stock-items", response_model=StockItemOut)
def create_stock_item(payload: StockItemCreate, db: Session = Depends(get_db)):
    item = StockItem(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        # SKU is unique. Without this the constraint violation escapes as a bare 500,
        # which reads as "the service is broken" rather than "you already have this SKU"
        # — and it is what made re-running the seed script abort mid-way.
        db.rollback()
        raise HTTPException(409, f"A stock item with SKU '{payload.sku}' already exists")
    db.refresh(item)
    return item


@router.get("/stock-items", response_model=list[StockItemOut])
def list_stock_items(db: Session = Depends(get_db)):
    return db.execute(select(StockItem)).scalars().all()


@router.get("/stock-items/{stock_item_id}", response_model=StockItemOut)
def get_stock_item(stock_item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(404, "Stock item not found")
    return item


@router.post("/stock-items/{stock_item_id}/batches", response_model=StockBatchOut)
def add_batch(stock_item_id: uuid.UUID, payload: StockBatchCreate, db: Session = Depends(get_db)):
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(404, "Stock item not found")
    batch = StockBatch(stock_item_id=stock_item_id, **payload.model_dump())
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/stock-items/{stock_item_id}/batches", response_model=list[StockBatchOut])
def list_batches(stock_item_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.execute(select(StockBatch).where(StockBatch.stock_item_id == stock_item_id)).scalars().all()


@router.post("/reservations", response_model=ReservationResult)
def create_reservation(payload: ReservationRequest, db: Session = Depends(get_db)):
    reservations, reserved_qty, shortfall = reserve_stock(db, payload.stock_item_id, payload.quantity, payload.request_id)
    return ReservationResult(
        reservations=reservations, reserved_quantity=reserved_qty, shortfall=shortfall, backorder_created=shortfall > 0,
    )


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(request_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = select(Reservation)
    if request_id:
        query = query.where(Reservation.request_id == request_id)
    return db.execute(query).scalars().all()


@router.get("/backorders", response_model=list[BackorderOut])
def list_backorders(db: Session = Depends(get_db)):
    return db.execute(select(Backorder).order_by(Backorder.created_at.desc())).scalars().all()


@router.post("/sweep-expired")
def sweep_expired(db: Session = Depends(get_db)):
    count = sweep_expired_reservations(db)
    return {"released": count}
