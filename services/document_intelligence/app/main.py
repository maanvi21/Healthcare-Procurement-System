from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.schema_bootstrap import bootstrap_schema
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "document_intelligence"}
