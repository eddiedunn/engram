"""Configuration management for Engram."""

from functools import lru_cache
from typing import Annotated, Any

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_KEY_MIN_LENGTH = 32


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ENGRAM_",
        case_sensitive=False,
    )

    # Database
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://engram:engram@localhost:5432/engram"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Embed service configuration
    embed_service_url: str = "http://localhost:8710"
    embed_timeout: float = 60.0
    embed_batch_size: int = 50
    embed_enabled: bool = True  # Can disable for testing
    embedding_dimensions: int = 1024  # bge-m3 dimensions

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8800
    api_reload: bool = False
    # Empty (the default) leaves /api/v1 open. When set, every /api/v1 request needs
    # "Authorization: Bearer <one of these keys>". Comma-separated, one key per client, so a
    # client can be cut off by removing its key. /health stays open for container health checks.
    api_keys: Annotated[list[str], NoDecode] = []

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

    @field_validator("api_keys", mode="before")
    @classmethod
    def split_api_keys(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [key.strip() for key in v.split(",") if key.strip()]
        return v

    @field_validator("api_keys")
    @classmethod
    def api_keys_long_enough(cls, v: list[str]) -> list[str]:
        if any(len(key) < API_KEY_MIN_LENGTH for key in v):
            raise ValueError(f"each API key must be at least {API_KEY_MIN_LENGTH} characters")
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str) -> str:
        """Ensure asyncpg driver is used."""
        if isinstance(v, str) and "postgresql://" in v and "asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
