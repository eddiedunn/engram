"""Client-side models (mirrors server models without heavy deps)."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ContentType(StrEnum):
    """Supported content types."""

    YOUTUBE = "youtube"
    ARTICLE = "article"
    PODCAST = "podcast"
    DOCUMENT = "document"
    NOTE = "note"
    OTHER = "other"


class Content(BaseModel):
    """Stored content."""

    id: str
    content_id: str
    content_type: ContentType
    title: str
    url: str | None
    text: str
    summary: str | None
    metadata: dict[str, Any]
    tags: list[str]
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class SearchResult(BaseModel):
    """Search result with relevance score."""

    content: Content
    chunk_text: str
    chunk_index: int
    score: float = Field(..., ge=0.0, le=1.0)
    search_type: str


class StoreResponse(BaseModel):
    """Response from store operation."""

    id: str
    content_id: str
    chunk_count: int
    message: str
