"""
config.py — reads all settings from the .env file using pydantic-settings.
Every other module imports `settings` from here instead of calling os.getenv directly.
This ensures a single source of truth and gives us type safety on every setting.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL connection string — for tests we allow SQLite via TEST_DATABASE_URL
    DATABASE_URL: str = "sqlite:///./skillbridge.db"

    # JWT signing key — must be a long random string in production
    SECRET_KEY: str = "change-me-in-production"

    # Algorithm used to sign JWTs (HS256 is HMAC-SHA256)
    ALGORITHM: str = "HS256"

    # Standard token lives for 24 hours (1440 minutes)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Monitoring-scoped token lives for only 1 hour
    MONITORING_TOKEN_EXPIRE_MINUTES: int = 60

    # API key required to exchange a standard MO token for a monitoring-scoped token
    MONITORING_API_KEY: str = "skillbridge-monitoring-key-2024"

    class Config:
        # Reads from .env in the project root (or wherever uvicorn is launched from)
        env_file = ".env"
        extra = "ignore"


# Module-level singleton — import this everywhere
settings = Settings()