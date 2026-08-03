from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.routers.approvals import router as approvals_router
from app.temporal_worker import start_worker_task

app = FastAPI(title="MediSource AI — Approval Workflow", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(approvals_router)


@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)
    start_worker_task()


@app.get("/health")
def health():
    return {"status": "ok", "service": "approval_workflow"}
