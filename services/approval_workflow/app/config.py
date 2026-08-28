from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_approvals"
    kafka_bootstrap_servers: str = "localhost:29092"
    redis_host: str = "localhost"
    redis_port: int = 6379
    opa_url: str = "http://localhost:8181"
    # Used to look up a vendor's current risk band when a request is raised without one.
    risk_intelligence_url: str = "http://localhost:8006"
    risk_lookup_timeout_seconds: float = 3.0
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "approval-workflow-queue"
    dedup_window_seconds: int = 60

    # Documents carry no department/category of their own — a real deployment would derive
    # these from the requesting ward or the PO header. These defaults decide which OPA
    # approval chain a document-raised request is routed through.
    document_default_department: str = "pharmacy"
    document_default_category: str = "pharmaceuticals"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
