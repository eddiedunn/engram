"""Smoke tests that verify the package imports without errors."""


def test_import_engram() -> None:
    import engram

    assert hasattr(engram, "__version__")
    assert engram.__version__ == "0.1.0"


def test_import_models() -> None:
    from engram.models import Content, ContentCreate, ContentType, SearchResult

    assert ContentType.YOUTUBE == "youtube"


def test_import_chunker() -> None:
    from engram.embedding.chunker import Chunker, ChunkingStrategy, TextChunk

    assert ChunkingStrategy.SEMANTIC_500 == "semantic_500"


def test_import_config() -> None:
    from engram.config import Settings, get_settings

    assert callable(get_settings)
