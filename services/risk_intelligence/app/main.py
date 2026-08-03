import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.kafka_consumer import start_consumer_thread
from app.mlflow_utils import get_or_train_model
from app.routers.risk import router as risk_router

logger = logging.getLogger("risk_intelligence.main")

app = FastAPI(title="MediSource AI — Risk Intelligence", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(risk_router)


def _warm_model():
    try:
        get_or_train_model()
    except Exception:
        logger.exception("Initial model warm-up failed — will retry lazily on first /risk/assess call")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    # training touches MLflow over the network — do it off the startup critical path
    threading.Thread(target=_warm_model, daemon=True, name="model-warmup").start()
    start_consumer_thread()


@app.get("/health")
def health():
    return {"status": "ok", "service": "risk_intelligence"}
