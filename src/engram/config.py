"""Configuration management for Engram."""

from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

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
