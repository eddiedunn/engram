"""Tests for the optional API key check (ENGRAM_API_KEYS). No DB connection needed."""

from collections.abc import AsyncGenerator

import httpx
import pytest
from pydantic import ValidationError

from engram.api.app import create_app
from engram.api.routes import get_repository
from engram.config import Settings

KEY_A = "a" * 32
KEY_B = "b" * 32


class FakeRepository:
    async def get_sources(self, content_type: object = None) -> dict[str, list[str]]:
        return {"meeting": ["someone"]}


async def fake_repository() -> AsyncGenerator[FakeRepository, None]:
    yield FakeRepository()


def client() -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[get_repository] = fake_repository
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


class TestApiKeysSetting:
    def test_off_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENGRAM_API_KEYS", raising=False)
        assert Settings().api_keys == []

    def test_comma_separated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENGRAM_API_KEYS", f" {KEY_A} , {KEY_B},")
        assert Settings().api_keys == [KEY_A, KEY_B]

    def test_short_key_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENGRAM_API_KEYS", "short")
        with pytest.raises(ValidationError):
            Settings()

    def test_old_single_key_name_does_not_turn_it_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # meeting-gram's env file has long set ENGRAM_API_KEY; it must stay inert.
        monkeypatch.delenv("ENGRAM_API_KEYS", raising=False)
        monkeypatch.setenv("ENGRAM_API_KEY", KEY_A)
        assert Settings().api_keys == []


class TestKeysUnset:
    async def test_api_open(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENGRAM_API_KEYS", raising=False)
        async with client() as c:
            r = await c.get("/api/v1/content/sources")
        assert r.status_code == 200


class TestKeysSet:
    @pytest.fixture(autouse=True)
    def _keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENGRAM_API_KEYS", f"{KEY_A},{KEY_B}")

    @pytest.mark.parametrize("headers", [
        {},
        {"Authorization": "Bearer " + "c" * 32},
        {"Authorization": KEY_A},
        {"Authorization": f"Basic {KEY_A}"},
        {"Authorization": "Bearer "},
    ])
    async def test_rejected(self, headers: dict[str, str]) -> None:
        async with client() as c:
            r = await c.get("/api/v1/content/sources", headers=headers)
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == "Bearer"

    async def test_rejected_on_writes_too(self) -> None:
        async with client() as c:
            r = await c.post("/api/v1/content", json={})
        assert r.status_code == 401

    @pytest.mark.parametrize("key", [KEY_A, KEY_B])
    async def test_each_key_accepted(self, key: str) -> None:
        async with client() as c:
            r = await c.get("/api/v1/content/sources", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200
        assert r.json() == {"meeting": ["someone"]}

    async def test_scheme_is_case_insensitive(self) -> None:
        async with client() as c:
            r = await c.get("/api/v1/content/sources", headers={"Authorization": f"bearer {KEY_A}"})
        assert r.status_code == 200

    async def test_health_stays_open(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The container health check calls /health without a key.
        from engram.embedding import Embedder

        async def healthy(self: Embedder) -> bool:
            return True

        monkeypatch.setattr(Embedder, "check_health", healthy)
        async with client() as c:
            r = await c.get("/health")
        assert r.status_code == 200
