from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_documents"
    kafka_bootstrap_servers: str = "localhost:29092"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "medisource_minio"
    minio_secret_key: str = "medisource_minio_secret"
    minio_secure: bool = False
    minio_bucket: str = "documents"

    # duplicate detection & review thresholds
    review_confidence_threshold: float = 0.75
    # a document scoring at/above this on the fraud screen goes to manual review
    fraud_review_threshold: float = 0.5

    # --- LLM (Groq) ---
    # Classification, field extraction and fraud screening use Groq when a key is set.
    # With no key the service falls back to the rule-based baselines and still works.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    llm_enabled: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
