"""Shared fixtures for engram tests."""

import os

import pytest


@pytest.fixture(autouse=True)
def _disable_embed_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable embed service calls in all tests by default."""
    monkeypatch.setenv("ENGRAM_EMBED_ENABLED", "false")


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Clear the lru_cache on get_settings between tests so env changes take effect."""
    from engram.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
