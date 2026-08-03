from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, SessionLocal, engine
from app.kafka_consumer import start_consumer_thread
from app.models import ContractTemplate
from app.routers.contracts import router as contracts_router
from app.templates import DEFAULT_TEMPLATES

app = FastAPI(title="MediSource AI — Contract Intelligence", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(contracts_router)


def _seed_templates() -> None:
    db = SessionLocal()
    try:
        for template_type, spec in DEFAULT_TEMPLATES.items():
            exists = db.query(ContractTemplate).filter(ContractTemplate.template_type == template_type).first()
            if not exists:
                db.add(ContractTemplate(template_type=template_type, **spec))
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
    return {"status": "ok", "service": "contract_intelligence"}
