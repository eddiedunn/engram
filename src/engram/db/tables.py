"""SQLAlchemy table definitions with pgvector support."""

from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from engram.config import get_settings
from engram.models.content import ContentType


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class ContentTable(Base):
    """Content storage table."""

    __tablename__ = "content"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    content_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type_enum"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    chunks: Mapped[list["ChunkTable"]] = relationship(
        "ChunkTable", back_populates="content", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_content_type", "content_type"),
        Index("ix_content_tags", "tags", postgresql_using="gin"),
        Index("ix_content_created_at", "created_at"),
    )


class ChunkTable(Base):
    """Text chunks with vector embeddings."""

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    content_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().embedding_dimensions), nullable=True
    )
    embedding_status: Mapped[str] = mapped_column(
        String(20), server_default='complete', nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    content: Mapped["ContentTable"] = relationship(
        "ContentTable", back_populates="chunks"
    )

    __table_args__ = (
        Index("ix_chunks_content_id", "content_id"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
