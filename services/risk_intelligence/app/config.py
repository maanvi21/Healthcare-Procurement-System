from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_risk"
    kafka_bootstrap_servers: str = "localhost:29092"
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_model_name: str = "vendor_risk_model"
    vendor_intelligence_url: str = "http://vendor_intelligence:8000"
    risk_band_low_max: float = 0.34
    risk_band_medium_max: float = 0.67

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
