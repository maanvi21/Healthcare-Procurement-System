from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.kafka_consumer import start_consumer_thread
from app.models import NotificationTemplate
from app.routers.notifications import router as notifications_router
from app.templates import DEFAULT_TEMPLATES

app = FastAPI(title="MediSource AI — Notification Agent", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(notifications_router)


def _seed_templates() -> None:
    db = SessionLocal()
    try:
        for spec in DEFAULT_TEMPLATES:
            exists = db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.event_type == spec["event_type"],
                    NotificationTemplate.channel == spec["channel"],
                    NotificationTemplate.name == spec["name"],
                )
            ).scalars().first()
            if not exists:
                db.add(NotificationTemplate(**spec))
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    _seed_templates()
    start_consumer_thread()


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification_agent"}
