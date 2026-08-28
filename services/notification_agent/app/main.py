from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.schema_bootstrap import bootstrap_schema
from app.kafka_consumer import start_consumer_thread
from app.models import NotificationTemplate
from app.routers.notifications import router as notifications_router
from app.templates import DEFAULT_TEMPLATES

app = FastAPI(title="MediSource AI — Notification Agent", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(notifications_router)


def _seed_templates() -> None:
    """Upsert the built-in templates.

    Insert-only seeding meant a fix to a DEFAULT_TEMPLATES body never reached an existing
    deployment: the row was already there, so the corrected template was silently ignored
    and the service kept rendering the old (wrong) text forever. Built-in templates are
    matched by their fixed name and re-synced on every startup, so editing
    DEFAULT_TEMPLATES is enough. Templates created through the API have different names
    and are never touched by this.
    """
    db = SessionLocal()
    try:
        for spec in DEFAULT_TEMPLATES:
            existing = db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.event_type == spec["event_type"],
                    NotificationTemplate.channel == spec["channel"],
                    NotificationTemplate.name == spec["name"],
                )
            ).scalars().first()
            if existing:
                existing.subject_template = spec["subject_template"]
                existing.body_template = spec["body_template"]
            else:
                db.add(NotificationTemplate(**spec))
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    bootstrap_schema(Base, engine, "a1b2c3d4e5f6")
    _seed_templates()
    start_consumer_thread()


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification_agent"}
