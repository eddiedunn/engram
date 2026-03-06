"""Tests for configuration loading (no DB connection needed)."""

import os

import pytest

from engram.config import Settings, get_settings


class TestSettings:
    """Settings defaults and overrides."""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Undo the autouse fixture that disables embed for safety
        monkeypatch.delenv("ENGRAM_EMBED_ENABLED", raising=False)
        settings = Settings()
        assert settings.api_port == 8800
        assert settings.api_host == "0.0.0.0"
        assert settings.db_pool_size == 5
        assert settings.embed_enabled is True
        assert settings.embedding_dimensions == 1024
        assert settings.log_level == "INFO"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENGRAM_API_PORT", "9999")
        monkeypatch.setenv("ENGRAM_LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.api_port == 9999
        assert settings.log_level == "DEBUG"

    def test_embed_disabled_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENGRAM_EMBED_ENABLED", "false")
        settings = Settings()
        assert settings.embed_enabled is False

    def test_database_url_default(self) -> None:
        settings = Settings()
        assert "asyncpg" in str(settings.database_url)

    def test_database_url_auto_asyncpg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If user provides postgresql:// without asyncpg, the validator adds it."""
        monkeypatch.setenv(
            "ENGRAM_DATABASE_URL",
            "postgresql://user:pass@host:5432/db",
        )
        settings = Settings()
        assert "asyncpg" in str(settings.database_url)


class TestGetSettings:
    """get_settings caching."""

    def test_returns_settings_instance(self) -> None:
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_cached(self) -> None:
        a = get_settings()
        b = get_settings()
        assert a is b
