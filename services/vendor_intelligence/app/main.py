from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.kafka_consumer import start_consumer_thread
from app.routers.vendors import router as vendors_router

app = FastAPI(title="MediSource AI — Vendor Intelligence", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(vendors_router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    start_consumer_thread()


@app.get("/health")
def health():
    return {"status": "ok", "service": "vendor_intelligence"}
