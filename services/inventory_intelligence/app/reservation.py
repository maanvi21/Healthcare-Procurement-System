"""Stock reservation logic: FEFO (first-expiry-first-out) allocation across batches,
Redis-locked per stock item to make concurrent reservations safe, with a hard rule that
cold-chain items are never split across batches (a partial cold-chain shipment from two
different batches is a compliance risk, not just an inventory nicety)."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.kafka_producer import publish_event
from app.models import Backorder, Reservation, ReservationStatus, StockBatch, StockItem
from app.redis_client import stock_item_lock


def _fefo_batches(db: Session, stock_item_id) -> list[StockBatch]:
    return (
        db.query(StockBatch)
        .filter(StockBatch.stock_item_id == stock_item_id, StockBatch.quantity_on_hand > 0)
        .order_by(StockBatch.expiry_date.asc().nulls_last())
        .all()
    )


def reserve_stock(db: Session, stock_item_id, quantity: int, request_id) -> tuple[list[Reservation], int, int]:
    stock_item = db.get(StockItem, stock_item_id)
    if not stock_item:
        raise ValueError("Unknown stock item")

    with stock_item_lock(str(stock_item_id)):
        batches = _fefo_batches(db, stock_item_id)
        expires_at = datetime.utcnow() + timedelta(hours=settings.reservation_hold_hours)
        reservations: list[Reservation] = []

        if stock_item.cold_chain:
            # must come from a single batch — no split shipments for cold-chain items
            eligible = next((b for b in batches if b.quantity_on_hand >= quantity), None)
            if eligible:
                eligible.quantity_on_hand -= quantity
                reservation = Reservation(
                    stock_item_id=stock_item_id, batch_id=eligible.id, request_id=request_id,
                    quantity=quantity, status=ReservationStatus.reserved, expires_at=expires_at,
                )
                db.add(reservation)
                reservations.append(reservation)
                reserved_qty = quantity
            else:
                reserved_qty = 0
        else:
            remaining = quantity
            for batch in batches:
                if remaining <= 0:
                    break
                take = min(batch.quantity_on_hand, remaining)
                if take <= 0:
                    continue
                batch.quantity_on_hand -= take
                reservation = Reservation(
                    stock_item_id=stock_item_id, batch_id=batch.id, request_id=request_id,
                    quantity=take, status=ReservationStatus.reserved, expires_at=expires_at,
                )
                db.add(reservation)
                reservations.append(reservation)
                remaining -= take
            reserved_qty = quantity - remaining

        shortfall = quantity - reserved_qty

        backorder = None
        if shortfall > 0:
            backorder = Backorder(
                stock_item_id=stock_item_id, request_id=request_id, quantity_short=shortfall,
                suggested_reorder_qty=max(stock_item.reorder_qty, shortfall),
            )
            db.add(backorder)

        db.commit()
        for r in reservations:
            db.refresh(r)

    if reservations:
        publish_event("inventory.reserved", str(request_id), {
            "request_id": str(request_id), "stock_item_id": str(stock_item_id), "quantity": reserved_qty,
        })
    if backorder:
        publish_event("inventory.backorder", str(request_id), {
            "request_id": str(request_id), "stock_item_id": str(stock_item_id), "quantity_short": shortfall,
        })

    return reservations, reserved_qty, shortfall


def release_reservations_for_request(db: Session, request_id) -> int:
    """Used when a procurement request is rejected — returns reserved stock to its batch."""
    reservations = db.query(Reservation).filter(
        Reservation.request_id == request_id, Reservation.status == ReservationStatus.reserved,
    ).all()
    count = 0
    for reservation in reservations:
        batch = db.get(StockBatch, reservation.batch_id)
        if batch:
            batch.quantity_on_hand += reservation.quantity
        reservation.status = ReservationStatus.released
        count += 1
    db.commit()
    return count


def sweep_expired_reservations(db: Session) -> int:
    now = datetime.utcnow()
    reservations = db.query(Reservation).filter(
        Reservation.status == ReservationStatus.reserved, Reservation.expires_at < now,
    ).all()
    count = 0
    for reservation in reservations:
        batch = db.get(StockBatch, reservation.batch_id)
        if batch:
            batch.quantity_on_hand += reservation.quantity
        reservation.status = ReservationStatus.expired
        count += 1
    db.commit()
    return count
