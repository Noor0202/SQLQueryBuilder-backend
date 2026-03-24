# backend/settings.py
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import SecretStr, validator
import os

class Settings(BaseSettings):
    # ---- Preferred: full DB URL provided via .env ----
    DATABASE_URL: Optional[str] = None

    # ---- Fallback DB components (use if you don't want a full URL) ----
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = None
    DB_USER: Optional[str] = None
    DB_PASS: Optional[str] = None
    DB_NAME: Optional[str] = None

    # ---- Security ----
    JWT_SECRET: SecretStr = SecretStr("super_secret_key_change_this_in_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    BCRYPT_SALT_ROUNDS: int = 12

    # ---- CORS ----
    # Default to strictly allow Vite frontend. Override via .env in production.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Environment / Logging ----
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # ---- Optional DB tuning (dev-safe defaults) ----
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # ---------------------
    # Convenience properties
    # ---------------------
    @property
    def cors_origins_list(self) -> List[str]:
        """Splits the comma-separated ALLOWED_ORIGINS string into a list."""
        return [origin.strip() for origin in (self.ALLOWED_ORIGINS or "").split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        """
        Return a canonical DATABASE_URL. Priority:
         1) Explicit DATABASE_URL from .env
         2) Build from DB_* components
        Raises ValueError if neither is properly configured.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL

        if all([self.DB_HOST, self.DB_PORT, self.DB_USER, self.DB_PASS, self.DB_NAME]):
            return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

        raise ValueError(
            "DATABASE_URL is not set and DB_* components are incomplete. "
            "Please set DATABASE_URL in .env or set DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME."
        )

    @validator("LOG_LEVEL")
    def _validate_log_level(cls, v: str) -> str:
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        val = (v or "INFO").upper()
        if val not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}")
        return val

# Create a single shared instance
settings = Settings()