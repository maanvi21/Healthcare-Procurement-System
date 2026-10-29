from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
import re

from app.db import Base, SessionLocal, engine
from app.schema_bootstrap import bootstrap_schema
from app.kafka_consumer import start_consumer_thread
from app.models import NotificationChannel, NotificationTemplate
from app.routers.notifications import router as notifications_router
from app.templates import DEFAULT_TEMPLATES

app = FastAPI(title="MediSource AI — Notification Agent", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(notifications_router)


def _seed_templates() -> None:
    """Migrate old channel templates to email and seed missing event templates."""
    db = SessionLocal()
    try:
        specs_by_event = {spec["event_type"]: spec for spec in DEFAULT_TEMPLATES}
        for template in db.execute(select(NotificationTemplate)).scalars():
            if template.channel != NotificationChannel.email:
                template.channel = NotificationChannel.email
                default = specs_by_event.get(template.event_type)
                if default and re.search(r"\((?:slack|sms|teams)\)", template.name, re.IGNORECASE):
                    template.name = default["name"]
                    if not template.subject_template:
                        template.subject_template = default.get("subject_template")

        for spec in DEFAULT_TEMPLATES:
            existing = db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.event_type == spec["event_type"],
                )
            ).scalars().first()
            if not existing:
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
