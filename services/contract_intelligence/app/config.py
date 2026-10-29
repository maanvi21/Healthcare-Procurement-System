from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_contracts"
    kafka_bootstrap_servers: str = "localhost:29092"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "medisource_minio"
    minio_secret_key: str = "medisource_minio_secret"
    minio_secure: bool = False
    minio_bucket: str = "contracts"
    opensign_base_url: str = "https://sandbox.opensignlabs.com/api/v1.2"
    opensign_api_key: str = ""
    opensign_webhook_secret: str = ""
    opensign_file_hosts: str = "digitaloceanspaces.com"
    esign_demo_mode: bool = False
    opa_url: str = "http://opa:8181"
    default_renewal_reminder_days: int = 30
    hospital_name: str = "MediSource General Hospital"
    approval_workflow_url: str = "http://approval_workflow:8000"
    vendor_intelligence_url: str = "http://vendor_intelligence:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
