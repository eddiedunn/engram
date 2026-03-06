"""Tests for Pydantic domain models."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from engram.models import Content, ContentCreate, ContentType, SearchResult


class TestContentType:
    """ContentType enum values."""

    def test_all_types_exist(self) -> None:
        assert ContentType.YOUTUBE == "youtube"
        assert ContentType.ARTICLE == "article"
        assert ContentType.PODCAST == "podcast"
        assert ContentType.DOCUMENT == "document"
        assert ContentType.NOTE == "note"
        assert ContentType.OTHER == "other"

    def test_string_coercion(self) -> None:
        assert str(ContentType.YOUTUBE) == "youtube"


class TestContentCreate:
    """ContentCreate validation."""

    def test_valid_content(self) -> None:
        content = ContentCreate(
            content_id="yt-abc123",
            content_type=ContentType.YOUTUBE,
            title="Test Video",
            text="This is the transcript of the video.",
        )
        assert content.content_id == "yt-abc123"
        assert content.content_type == ContentType.YOUTUBE
        assert content.url is None
        assert content.metadata == {}
        assert content.tags == []

    def test_full_content(self) -> None:
        content = ContentCreate(
            content_id="art-1",
            content_type=ContentType.ARTICLE,
            title="An Article",
            url="https://example.com/article",
            text="Article body text.",
            summary="A short summary.",
            metadata={"author": "Jane"},
            tags=["tech", "ai"],
        )
        assert content.url == "https://example.com/article"
        assert content.summary == "A short summary."
        assert content.metadata == {"author": "Jane"}
        assert content.tags == ["tech", "ai"]

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ContentCreate(
                content_id="bad",
                content_type=ContentType.NOTE,
                title="",
                text="some text",
            )

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ContentCreate(
                content_id="bad",
                content_type=ContentType.NOTE,
                title="Title",
                text="",
            )

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ContentCreate(title="No ID", text="body")  # type: ignore[call-arg]


class TestContent:
    """Content (stored) model."""

    def test_roundtrip(self) -> None:
        now = datetime.now(timezone.utc)
        uid = uuid4()
        content = Content(
            id=uid,
            content_id="test-1",
            content_type=ContentType.DOCUMENT,
            title="Doc",
            url=None,
            text="Body.",
            summary=None,
            metadata={},
            tags=[],
            chunk_count=3,
            created_at=now,
            updated_at=now,
        )
        assert content.id == uid
        assert content.chunk_count == 3

    def test_json_serialization(self) -> None:
        now = datetime.now(timezone.utc)
        content = Content(
            id=uuid4(),
            content_id="ser-1",
            content_type=ContentType.NOTE,
            title="Note",
            url=None,
            text="Body.",
            summary=None,
            metadata={"key": "value"},
            tags=["tag1"],
            chunk_count=1,
            created_at=now,
            updated_at=now,
        )
        data = content.model_dump(mode="json")
        assert data["content_type"] == "note"
        assert data["metadata"] == {"key": "value"}


class TestSearchResult:
    """SearchResult model."""

    def test_valid_result(self) -> None:
        now = datetime.now(timezone.utc)
        result = SearchResult(
            content=Content(
                id=uuid4(),
                content_id="sr-1",
                content_type=ContentType.ARTICLE,
                title="Result",
                url=None,
                text="Full text.",
                summary=None,
                metadata={},
                tags=[],
                chunk_count=1,
                created_at=now,
                updated_at=now,
            ),
            chunk_text="matched chunk",
            chunk_index=0,
            score=0.85,
            search_type="semantic",
        )
        assert result.score == 0.85
        assert result.search_type == "semantic"

    def test_score_bounds(self) -> None:
        now = datetime.now(timezone.utc)
        base = {
            "content": Content(
                id=uuid4(),
                content_id="bounds",
                content_type=ContentType.NOTE,
                title="T",
                url=None,
                text="T",
                summary=None,
                metadata={},
                tags=[],
                chunk_count=0,
                created_at=now,
                updated_at=now,
            ),
            "chunk_text": "t",
            "chunk_index": 0,
            "search_type": "fts",
        }
        # score=0.0 is valid
        SearchResult(score=0.0, **base)
        # score=1.0 is valid
        SearchResult(score=1.0, **base)
        # score > 1.0 is rejected
        with pytest.raises(ValidationError):
            SearchResult(score=1.5, **base)
        # score < 0.0 is rejected
        with pytest.raises(ValidationError):
            SearchResult(score=-0.1, **base)
