from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_approvals"
    kafka_bootstrap_servers: str = "localhost:29092"
    redis_host: str = "localhost"
    redis_port: int = 6379
    opa_url: str = "http://localhost:8181"
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "approval-workflow-queue"
    dedup_window_seconds: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
