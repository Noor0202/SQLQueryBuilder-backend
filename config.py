# backend/config.py
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import SecretStr, validator

class Settings(BaseSettings):
    # --- Database Components ---
    DATABASE_URL: Optional[str] = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASS: str = "root"
    DB_NAME: str = "sqlbuilder_db"

    # --- Server Components ---
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    APP_RELOAD: bool = True
    ENVIRONMENT: str = "development"

    # --- Security ---
    JWT_SECRET: SecretStr = SecretStr("change_this_to_a_secure_random_string_in_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    BCRYPT_SALT_ROUNDS: int = 12

    # --- CORS & Logging ---
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    LOG_LEVEL: str = "INFO"

    # --- MISSING DB TUNING (CRITICAL FIX) ---
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        """Splits the comma-separated ALLOWED_ORIGINS string into a list."""
        return [origin.strip() for origin in (self.ALLOWED_ORIGINS or "").split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        """Builds the database URL from .env components."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @validator("LOG_LEVEL", pre=True)
    def _validate_log_level(cls, v: str) -> str:
        valid = {"INFO", "WARNING", "ERROR"}
        val = (v or "INFO").upper()
        if val not in valid:
            return "INFO"
        return val

settings = Settings()