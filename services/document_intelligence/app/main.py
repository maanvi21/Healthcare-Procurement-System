from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.schema_bootstrap import bootstrap_schema
from app.kafka_consumer import start_consumer_thread
from app.file_watcher import start_watcher_thread
from app.routers.documents import router as documents_router

app = FastAPI(title="MediSource AI — Document Intelligence", version="1.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(documents_router)


@app.on_event("startup")
def on_startup():
    # Alembic migrations are the source of truth; this is a convenience fallback so the
    # service also works if someone runs `docker-compose up` without the deploy script.
    bootstrap_schema(Base, engine, "fd0120855bdf")
    # Processes documents.ingested — the OCR/extraction pipeline runs here, not in the
    # upload request. See app/kafka_consumer.py.
    start_consumer_thread()
    # Watches watched_documents/ for new files dropped by staff and auto-ingests them
    # into the same pipeline. See app/file_watcher.py.
    start_watcher_thread()


@app.get("/health")
def health():
    return {"status": "ok", "service": "document_intelligence"}
