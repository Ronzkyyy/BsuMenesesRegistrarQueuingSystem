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
    # Secure by default: an operator who forgets to set DEBUG in production
    # env vars gets the locked-down posture (no docs, HSTS, strict CSP), not
    # the permissive dev one. Local dev's backend/.env sets DEBUG=True
    # explicitly (see dev.ps1), so this default only matters when DEBUG is
    # never set at all.
    DEBUG: bool = False
    LOG_LEVEL: str = "info"

    # Brute-force protection for staff login: lock an account after this many
    # consecutive failed attempts, for this many minutes.
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # Optional explicit bootstrap for the first admin account in a fresh
    # production deployment (see app/core/init_db.py) - deliberately has no
    # default password, unlike the DEBUG-only demo accounts.
    INITIAL_ADMIN_USERNAME: str = ""
    INITIAL_ADMIN_PASSWORD: str = ""

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

# Fail fast rather than silently signing every JWT with a secret anyone can
# read in this public repo's source. Only enforced outside DEBUG - local dev
# is free to leave SECRET_KEY unset.
if not settings.DEBUG and settings.SECRET_KEY == "your-secret-key-here":
    raise RuntimeError(
        "SECRET_KEY is still the placeholder value - set a real secret via "
        "the SECRET_KEY environment variable before running with DEBUG=False."
    )