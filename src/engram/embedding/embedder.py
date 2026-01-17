"""Embedding generation service using sentence-transformers."""

import structlog
from sentence_transformers import SentenceTransformer

from engram.config import get_settings

logger = structlog.get_logger()


class Embedder:
    """Generates embeddings using sentence-transformers models."""

    _instance: "Embedder | None" = None
    _model: SentenceTransformer | None = None

    def __new__(cls) -> "Embedder":
        """Singleton pattern for model reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize embedder (model loaded lazily)."""
        self.settings = get_settings()
        self.model_name = self.settings.embedding_model
        self.batch_size = self.settings.embedding_batch_size

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info("Loading embedding model", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info(
                "Model loaded",
                model=self.model_name,
                dimensions=self._model.get_sentence_embedding_dimension(),
            )
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.debug("Embedding batch", count=len(texts), batch_size=self.batch_size)
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > self.batch_size,
        )
        return [e.tolist() for e in embeddings]

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions from loaded model."""
        return self.model.get_sentence_embedding_dimension()
