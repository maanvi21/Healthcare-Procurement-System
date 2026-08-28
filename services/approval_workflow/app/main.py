import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.schema_bootstrap import bootstrap_schema
from app.kafka_consumer import start_consumer_thread
from app.routers.approvals import router as approvals_router
from app.temporal_worker import start_worker_task

app = FastAPI(title="MediSource AI — Approval Workflow", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(approvals_router)


@app.on_event("startup")
async def on_startup():
    bootstrap_schema(Base, engine, "b36030ce9776")
    start_worker_task()
    # the consumer thread submits async work back to this loop — see kafka_consumer
    start_consumer_thread(asyncio.get_running_loop())


@app.get("/health")
def health():
    return {"status": "ok", "service": "approval_workflow"}
