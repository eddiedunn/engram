"""Content domain models."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentType(StrEnum):
    """Supported content types."""

    YOUTUBE = "youtube"
    ARTICLE = "article"
    PODCAST = "podcast"
    DOCUMENT = "document"
    NOTE = "note"
    OTHER = "other"


class ContentCreate(BaseModel):
    """Schema for creating new content."""

    content_id: str = Field(..., description="External unique identifier")
    content_type: ContentType = Field(..., description="Type of content")
    title: str = Field(..., min_length=1, max_length=500)
    url: str | None = Field(None, max_length=2000)
    text: str = Field(..., min_length=1, description="Full text content")
    summary: str | None = Field(None, description="Optional summary")
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class Content(BaseModel):
    """Stored content with database fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
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


class ChunkCreate(BaseModel):
    """Schema for creating a chunk."""

    content_id: UUID
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    embedding: list[float] | None = None


class Chunk(BaseModel):
    """Stored chunk with embedding."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_id: UUID
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    created_at: datetime


class SearchResult(BaseModel):
    """Search result with relevance score."""

    content: Content
    chunk_text: str
    chunk_index: int
    score: float = Field(..., ge=0.0, le=1.0)
    search_type: str = Field(..., description="'semantic', 'fts', or 'hybrid'")
