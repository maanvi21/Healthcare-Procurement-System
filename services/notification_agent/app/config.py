from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_notifications"
    kafka_bootstrap_servers: str = "localhost:29092"
    # Set this to a real internal mailbox for events without an explicit email recipient.
    default_notification_recipient: str = ""
    vendor_intelligence_url: str = "http://vendor_intelligence:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
