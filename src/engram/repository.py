"""Repository layer for content storage and retrieval."""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog
from pgvector.sqlalchemy import Vector
from sqlalchemy import delete, select, text, cast, update
from sqlalchemy.ext.asyncio import AsyncSession

from engram.db.tables import ChunkTable, ContentTable
from engram.embedding import Chunker, ChunkingStrategy, Embedder
from engram.models import Content, ContentCreate, ContentType, SearchResult

logger = structlog.get_logger()


class ContentRepository:
    """Repository for content CRUD and search operations."""

    def __init__(
        self,
        session: AsyncSession,
        embedder: Embedder | None = None,
        chunker: Chunker | None = None,
    ):
        """Initialize repository with database session.

        Args:
            session: Async database session
            embedder: Embedder instance (created if not provided)
            chunker: Chunker instance (created if not provided)
        """
        self.session = session
        self.embedder = embedder or Embedder()
        self.chunker = chunker or Chunker(strategy=ChunkingStrategy.SEMANTIC_500)

    async def store(self, content: ContentCreate) -> Content:
        """Store content with chunking and embedding.

        Args:
            content: Content to store

        Returns:
            Stored content with ID
        """
        # Check if content already exists
        existing = await self.get_by_content_id(content.content_id)
        if existing:
            logger.info("Updating existing content", content_id=content.content_id)
            return await self._update_content(existing.id, content)

        logger.info("Storing new content", content_id=content.content_id, type=content.content_type)

        # Create content record
        content_row = ContentTable(
            content_id=content.content_id,
            content_type=content.content_type,
            title=content.title,
            url=content.url,
            text=content.text,
            summary=content.summary,
            metadata_=content.metadata,
            tags=content.tags,
        )
        self.session.add(content_row)
        await self.session.flush()  # Get the ID

        # Chunk and embed
        chunks = self.chunker.chunk(content.text)
        chunk_texts = [c.text for c in chunks]
        # Run embedding in thread pool to avoid blocking async event loop
        embeddings = await asyncio.to_thread(self.embedder.embed_batch, chunk_texts)

        # Handle embedding service unavailability
        if embeddings is None:
            logger.warning(
                "Embed service unavailable, storing content without embeddings",
                content_id=content.content_id,
            )
            # Store chunks with None embeddings (pending status)
            for chunk in chunks:
                chunk_row = ChunkTable(
                    content_id=content_row.id,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    embedding=None,
                    embedding_status='pending',
                )
                self.session.add(chunk_row)
        else:
            # Store chunks with embeddings
            for chunk, embedding in zip(chunks, embeddings):
                chunk_row = ChunkTable(
                    content_id=content_row.id,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    embedding=embedding,
                    embedding_status='complete',
                )
                self.session.add(chunk_row)

        content_row.chunk_count = len(chunks)
        await self.session.commit()  # Explicit commit to ensure pgvector operations complete

        # Refresh to avoid lazy loading issues
        await self.session.refresh(content_row)

        logger.info(
            "Content stored",
            content_id=content.content_id,
            chunks=len(chunks),
        )

        return self._to_model(content_row)

    async def _update_content(self, id: UUID, content: ContentCreate) -> Content:
        """Update existing content, re-chunk and re-embed."""
        # Delete existing chunks
        await self.session.execute(
            delete(ChunkTable).where(ChunkTable.content_id == id)
        )

        # Get and update content row
        result = await self.session.execute(
            select(ContentTable).where(ContentTable.id == id)
        )
        content_row = result.scalar_one()

        content_row.title = content.title
        content_row.url = content.url
        content_row.text = content.text
        content_row.summary = content.summary
        content_row.metadata_ = content.metadata
        content_row.tags = content.tags

        # Re-chunk and embed
        chunks = self.chunker.chunk(content.text)
        chunk_texts = [c.text for c in chunks]
        # Run embedding in thread pool to avoid blocking async event loop
        embeddings = await asyncio.to_thread(self.embedder.embed_batch, chunk_texts)

        # Handle embedding service unavailability
        if embeddings is None:
            logger.warning(
                "Embed service unavailable, updating content without embeddings",
                content_id=content.content_id,
            )
            # Store chunks with None embeddings
            for chunk in chunks:
                chunk_row = ChunkTable(
                    content_id=id,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    embedding=None,
                    embedding_status='pending',
                )
                self.session.add(chunk_row)
        else:
            for chunk, embedding in zip(chunks, embeddings):
                chunk_row = ChunkTable(
                    content_id=id,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    embedding=embedding,
                    embedding_status='complete',
                )
                self.session.add(chunk_row)

        content_row.chunk_count = len(chunks)
        return self._to_model(content_row)

    async def get(self, id: UUID) -> Content | None:
        """Get content by internal ID."""
        result = await self.session.execute(
            select(ContentTable).where(ContentTable.id == id)
        )
        row = result.scalar_one_or_none()
        return self._to_model(row) if row else None

    async def get_by_content_id(self, content_id: str) -> Content | None:
        """Get content by external content ID."""
        result = await self.session.execute(
            select(ContentTable).where(ContentTable.content_id == content_id)
        )
        row = result.scalar_one_or_none()
        return self._to_model(row) if row else None

    async def delete(self, id: UUID) -> bool:
        """Delete content by ID."""
        result = await self.session.execute(
            delete(ContentTable).where(ContentTable.id == id)
        )
        return result.rowcount > 0

    async def list(
        self,
        content_type: ContentType | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Content]:
        """List content with optional filters."""
        query = select(ContentTable).order_by(ContentTable.created_at.desc())

        if content_type:
            query = query.where(ContentTable.content_type == content_type)

        if tags:
            # Array contains any of the specified tags
            query = query.where(ContentTable.tags.overlap(tags))

        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return [self._to_model(row) for row in result.scalars()]

    async def get_chunks_by_status(
        self, status: str, limit: int = 50
    ) -> list[ChunkTable]:
        """Get chunks by embedding status.

        Args:
            status: Embedding status ('pending', 'complete', 'failed')
            limit: Maximum number of chunks to return

        Returns:
            List of chunk rows matching the status
        """
        result = await self.session.execute(
            select(ChunkTable)
            .where(ChunkTable.embedding_status == status)
            .limit(limit)
        )
        return list(result.scalars().all())


    async def update_chunk_embedding(
        self, chunk_id: UUID, embedding: list[float]
    ) -> None:
        """Update chunk with generated embedding.

        Args:
            chunk_id: UUID of the chunk to update
            embedding: Generated embedding vector

        Used by backfill script to populate pending embeddings.
        """
        await self.session.execute(
            update(ChunkTable)
            .where(ChunkTable.id == chunk_id)
            .values(
                embedding=embedding,
                embedding_status='complete'
            )
        )
        await self.session.commit()

    async def search_semantic(
        self,
        query: str,
        top_k: int = 10,
        content_type: ContentType | None = None,
        tags: list[str] | None = None,
        threshold: float = 0.0,
    ) -> list[SearchResult]:
        """Semantic search using vector similarity.

        Args:
            query: Search query text
            top_k: Maximum results to return
            content_type: Filter by content type
            tags: Filter by tags (any match)
            threshold: Minimum similarity score (0-1)

        Returns:
            List of search results ordered by relevance
        """
        # Generate query embedding
        # Run embedding in thread pool to avoid blocking async event loop
        query_embedding = await asyncio.to_thread(self.embedder.embed, query)

        # If embedding service unavailable, return empty results
        if query_embedding is None:
            logger.warning("Embed service unavailable for search", query=query)
            return []

        # Build the query with pgvector cosine distance
        # Note: pgvector uses distance, so we convert to similarity (1 - distance)
        from sqlalchemy import bindparam

        sql = """
            SELECT
                c.id as content_id,
                c.content_id as external_id,
                c.content_type,
                c.title,
                c.url,
                c.text,
                c.summary,
                c.metadata,
                c.tags,
                c.chunk_count,
                c.created_at,
                c.updated_at,
                ch.text as chunk_text,
                ch.chunk_index,
                1 - (ch.embedding <=> :embedding) as score
            FROM chunks ch
            JOIN content c ON ch.content_id = c.id
            WHERE ch.embedding IS NOT NULL
        """

        params: dict = {"embedding": query_embedding}

        if content_type:
            sql += " AND c.content_type = :content_type"
            params["content_type"] = content_type.value

        if tags:
            sql += " AND c.tags && :tags"
            params["tags"] = tags

        if threshold > 0:
            sql += " AND (1 - (ch.embedding <=> :embedding)) >= :threshold"
            params["threshold"] = threshold

        sql += " ORDER BY ch.embedding <=> :embedding LIMIT :limit"
        params["limit"] = top_k

        # Use bindparam with Vector type for proper parameter binding with asyncpg
        stmt = text(sql).bindparams(bindparam("embedding", type_=Vector(len(query_embedding))))
        result = await self.session.execute(stmt, params)
        rows = result.mappings().all()

        return [
            SearchResult(
                content=Content(
                    id=row["content_id"],
                    content_id=row["external_id"],
                    content_type=row["content_type"],
                    title=row["title"],
                    url=row["url"],
                    text=row["text"],
                    summary=row["summary"],
                    metadata=row["metadata"] or {},
                    tags=row["tags"] or [],
                    chunk_count=row["chunk_count"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ),
                chunk_text=row["chunk_text"],
                chunk_index=row["chunk_index"],
                score=float(row["score"]),
                search_type="semantic",
            )
            for row in rows
        ]

    async def search_fts(
        self,
        query: str,
        limit: int = 10,
        content_type: ContentType | None = None,
        tags: list[str] | None = None,
    ) -> list[SearchResult]:
        """Full-text search using PostgreSQL.

        Args:
            query: Search query (supports PostgreSQL tsquery syntax)
            limit: Maximum results
            content_type: Filter by content type
            tags: Filter by tags

        Returns:
            Search results with FTS ranking
        """
        # Use PostgreSQL full-text search
        sql = """
            SELECT
                c.id as content_id,
                c.content_id as external_id,
                c.content_type,
                c.title,
                c.url,
                c.text,
                c.summary,
                c.metadata,
                c.tags,
                c.chunk_count,
                c.created_at,
                c.updated_at,
                ch.text as chunk_text,
                ch.chunk_index,
                ts_rank(to_tsvector('english', ch.text), plainto_tsquery('english', :query)) as score
            FROM chunks ch
            JOIN content c ON ch.content_id = c.id
            WHERE to_tsvector('english', ch.text) @@ plainto_tsquery('english', :query)
        """

        params: dict = {"query": query}

        if content_type:
            sql += " AND c.content_type = :content_type"
            params["content_type"] = content_type.value

        if tags:
            sql += " AND c.tags && :tags"
            params["tags"] = tags

        sql += " ORDER BY score DESC LIMIT :limit"
        params["limit"] = limit

        result = await self.session.execute(text(sql), params)
        rows = result.mappings().all()

        # Normalize FTS scores to 0-1 range
        max_score = max((row["score"] for row in rows), default=1.0) or 1.0

        return [
            SearchResult(
                content=Content(
                    id=row["content_id"],
                    content_id=row["external_id"],
                    content_type=row["content_type"],
                    title=row["title"],
                    url=row["url"],
                    text=row["text"],
                    summary=row["summary"],
                    metadata=row["metadata"] or {},
                    tags=row["tags"] or [],
                    chunk_count=row["chunk_count"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ),
                chunk_text=row["chunk_text"],
                chunk_index=row["chunk_index"],
                score=float(row["score"]) / max_score,
                search_type="fts",
            )
            for row in rows
        ]

    async def search_hybrid(
        self,
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.7,
        content_type: ContentType | None = None,
        tags: list[str] | None = None,
    ) -> list[SearchResult]:
        """Hybrid search combining semantic and FTS.

        Args:
            query: Search query
            top_k: Maximum results
            semantic_weight: Weight for semantic search (0-1), FTS gets 1-weight
            content_type: Filter by content type
            tags: Filter by tags

        Returns:
            Combined and re-ranked results
        """
        # Run both searches
        semantic_results = await self.search_semantic(
            query, top_k=top_k * 2, content_type=content_type, tags=tags
        )
        fts_results = await self.search_fts(
            query, limit=top_k * 2, content_type=content_type, tags=tags
        )

        # Combine scores by content+chunk
        scores: dict[tuple[UUID, int], tuple[float, SearchResult]] = {}

        fts_weight = 1.0 - semantic_weight

        for result in semantic_results:
            key = (result.content.id, result.chunk_index)
            scores[key] = (result.score * semantic_weight, result)

        for result in fts_results:
            key = (result.content.id, result.chunk_index)
            if key in scores:
                existing_score, existing_result = scores[key]
                combined_score = existing_score + (result.score * fts_weight)
                scores[key] = (combined_score, existing_result)
            else:
                scores[key] = (result.score * fts_weight, result)

        # Sort by combined score and return top_k
        sorted_results = sorted(scores.values(), key=lambda x: x[0], reverse=True)

        return [
            SearchResult(
                content=result.content,
                chunk_text=result.chunk_text,
                chunk_index=result.chunk_index,
                score=score,
                search_type="hybrid",
            )
            for score, result in sorted_results[:top_k]
        ]

    def _to_model(self, row: ContentTable) -> Content:
        """Convert database row to domain model."""
        return Content(
            id=row.id,
            content_id=row.content_id,
            content_type=row.content_type,
            title=row.title,
            url=row.url,
            text=row.text,
            summary=row.summary,
            metadata=row.metadata_ or {},
            tags=row.tags or [],
            chunk_count=row.chunk_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
