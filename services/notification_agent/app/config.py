from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_notifications"
    kafka_bootstrap_servers: str = "localhost:29092"
    # Demo default recipient used when an event payload has no contact fields.
    default_notification_recipient: str = "procurement@medisource.local"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
