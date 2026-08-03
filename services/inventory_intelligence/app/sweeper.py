import logging
import threading
import time

from app.db import SessionLocal
from app.reservation import sweep_expired_reservations

logger = logging.getLogger("inventory_intelligence.sweeper")

SWEEP_INTERVAL_SECONDS = 300


def _sweep_loop():
    while True:
        time.sleep(SWEEP_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            count = sweep_expired_reservations(db)
            if count:
                logger.info("Released %d expired reservation(s)", count)
        except Exception:
            logger.exception("Reservation sweep failed")
        finally:
            db.close()


def start_sweeper_thread() -> None:
    threading.Thread(target=_sweep_loop, daemon=True, name="reservation-sweeper").start()
