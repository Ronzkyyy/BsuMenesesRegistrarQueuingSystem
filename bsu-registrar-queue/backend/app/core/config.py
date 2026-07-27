"""
Application configuration settings
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost/bsu_queue"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DEBUG: bool = True
    LOG_LEVEL: str = "info"

    # Comma-separated list of origins allowed to call the API cross-origin.
    # Set this to the real deployed frontend domain(s) in production.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # Queue settings
    MAX_QUEUE_SIZE: int = 100
    DEFAULT_SLOT_DURATION_MINUTES: int = 30

    # Campus-specific
    CAMPUS_NAME: str = "Bulacan State University - Meneses Campus"

    class Config:
        env_file = ".env"


settings = Settings()