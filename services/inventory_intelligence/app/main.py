from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.schema_bootstrap import bootstrap_schema
from app.kafka_consumer import start_consumer_thread
from app.routers.inventory import router as inventory_router
from app.sweeper import start_sweeper_thread

app = FastAPI(title="MediSource AI — Inventory Intelligence", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(inventory_router)


@app.on_event("startup")
def on_startup():
    bootstrap_schema(Base, engine, "70202e23f2d6")
    start_consumer_thread()
    start_sweeper_thread()


@app.get("/health")
def health():
    return {"status": "ok", "service": "inventory_intelligence"}
