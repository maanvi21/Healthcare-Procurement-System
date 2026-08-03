from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_vendors"
    kafka_bootstrap_servers: str = "localhost:29092"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
