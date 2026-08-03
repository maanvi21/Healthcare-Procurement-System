from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://medisource:medisource_dev_pw@localhost:5432/medisource_inventory"
    kafka_bootstrap_servers: str = "localhost:29092"
    redis_host: str = "localhost"
    redis_port: int = 6379
    reservation_hold_hours: int = 48

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
