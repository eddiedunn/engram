"""Embedding service client wrapper."""

import httpx
import structlog

from engram.config import get_settings

logger = structlog.get_logger()


class Embedder:
    """Generates embeddings via Embed service."""

    _instance: "Embedder | None" = None

    def __new__(cls) -> "Embedder":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=self.settings.embed_service_url,
            timeout=self.settings.embed_timeout,
        )
        self._available = True

    async def embed(self, text: str) -> list[float] | None:
        """Generate embedding for a single text."""
        result = await self.embed_batch([text])
        return result[0] if result else None

    _BATCH_SIZE = 100

    async def embed_batch(self, texts: list[str]) -> list[list[float]] | None:
        """Generate embeddings for multiple texts.

        Returns None if service unavailable (graceful degradation).
        Splits into batches of 100 to respect embed service limits.
        """
        if not texts:
            return []

        if not self._available or not self.settings.embed_enabled:
            return None

        try:
            all_embeddings: list[list[float]] = []
            for i in range(0, len(texts), self._BATCH_SIZE):
                batch = texts[i:i + self._BATCH_SIZE]
                response = await self._client.post("/v1/embed", json={"texts": batch})
                response.raise_for_status()
                all_embeddings.extend(response.json()["embeddings"])
            return all_embeddings
        except Exception as e:
            logger.warning("Embed service unavailable", error=str(e))
            self._available = False
            return None

    async def check_health(self) -> bool:
        """Check if embed service is healthy."""
        try:
            response = await self._client.get("/health")
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions (fixed for bge-m3)."""
        return 1024
