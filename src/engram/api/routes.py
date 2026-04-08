"""API routes for content management and search."""

from typing import Annotated, Any, AsyncGenerator
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from engram.db.connection import get_db
from engram.models import Content, ContentCreate, ContentListResponse, ContentType, SearchResult
from engram.repository import ContentRepository

logger = structlog.get_logger()

router = APIRouter(tags=["content"])


async def get_repository() -> AsyncGenerator[ContentRepository, None]:
    """Dependency to get repository with database session."""
    async with get_db() as session:
        yield ContentRepository(session)


RepoDep = Annotated[ContentRepository, Depends(get_repository)]


# Request/Response schemas
class StoreResponse(BaseModel):
    """Response for content storage."""

    id: UUID
    content_id: str
    chunk_count: int
    message: str = "Content stored successfully"


class SearchRequest(BaseModel):
    """Search request parameters."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(10, ge=1, le=100)
    content_type: ContentType | None = None
    tags: list[str] | None = None
    threshold: float = Field(0.0, ge=0.0, le=1.0)


class HybridSearchRequest(SearchRequest):
    """Hybrid search with weight parameter."""

    semantic_weight: float = Field(0.7, ge=0.0, le=1.0)


class MetadataPatchRequest(BaseModel):
    """PATCH request to merge keys into content.metadata."""

    metadata: dict[str, Any] = Field(..., description="Keys to merge into content.metadata (JSONB ||)")


class StatsResponse(BaseModel):
    """Corpus statistics."""

    total_content: int
    total_chunks: int
    by_type: dict[str, int]


# Routes
@router.post("/content", response_model=StoreResponse)
async def store_content(content: ContentCreate, repo: RepoDep) -> StoreResponse:
    """Store new content with automatic chunking and embedding."""
    try:
        stored = await repo.store(content)
        return StoreResponse(
            id=stored.id,
            content_id=stored.content_id,
            chunk_count=stored.chunk_count,
        )
    except Exception as e:
        logger.error("Failed to store content", error=str(e), content_id=content.content_id)
        raise HTTPException(status_code=500, detail=str(e))


# This route MUST be before /content/{content_id} to avoid the path parameter swallowing "sources".
@router.get("/content/sources")
async def get_sources(
    repo: RepoDep,
    content_type: ContentType | None = None,
) -> dict[str, list[str]]:
    """Get unique content sources (authors) grouped by content type."""
    try:
        return await repo.get_sources(content_type=content_type)
    except Exception as e:
        logger.error("Failed to get sources", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content/{content_id}", response_model=Content)
async def get_content(content_id: str, repo: RepoDep) -> Content:
    """Get content by external content ID."""
    content = await repo.get_by_content_id(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return content


@router.delete("/content/{content_id}")
async def delete_content(content_id: str, repo: RepoDep) -> dict:
    """Delete content by external content ID."""
    content = await repo.get_by_content_id(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    await repo.delete(content.id)
    return {"message": "Content deleted", "content_id": content_id}


@router.patch("/content/{content_id}", response_model=Content)
async def patch_content_metadata(
    content_id: str,
    request: MetadataPatchRequest,
    repo: RepoDep,
) -> Content:
    """Merge keys into content.metadata (JSONB ||). No re-chunk, no re-embed."""
    updated = await repo.merge_metadata(content_id, request.metadata)
    if not updated:
        raise HTTPException(status_code=404, detail="Content not found")
    return updated


@router.get("/content", response_model=ContentListResponse)
async def list_content(
    repo: RepoDep,
    content_type: ContentType | None = None,
    tags: Annotated[list[str] | None, Query()] = None,
    source: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ContentListResponse:
    """List content with optional filters. Returns paginated envelope with total count."""
    return await repo.list_with_count(
        content_type=content_type,
        tags=tags,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.post("/search/semantic", response_model=list[SearchResult])
async def search_semantic(request: SearchRequest, repo: RepoDep) -> list[SearchResult]:
    """Semantic search using vector similarity."""
    return await repo.search_semantic(
        query=request.query,
        top_k=request.top_k,
        content_type=request.content_type,
        tags=request.tags,
        threshold=request.threshold,
    )


@router.post("/search/fts", response_model=list[SearchResult])
async def search_fts(request: SearchRequest, repo: RepoDep) -> list[SearchResult]:
    """Full-text search using PostgreSQL."""
    return await repo.search_fts(
        query=request.query,
        limit=request.top_k,
        content_type=request.content_type,
        tags=request.tags,
    )


@router.post("/search/hybrid", response_model=list[SearchResult])
async def search_hybrid(request: HybridSearchRequest, repo: RepoDep) -> list[SearchResult]:
    """Hybrid search combining semantic and full-text search."""
    return await repo.search_hybrid(
        query=request.query,
        top_k=request.top_k,
        semantic_weight=request.semantic_weight,
        content_type=request.content_type,
        tags=request.tags,
    )


@router.get("/search", response_model=list[SearchResult])
async def search_get(
    repo: RepoDep,
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=100),
    content_type: ContentType | None = None,
    tags: Annotated[list[str] | None, Query()] = None,
    mode: str = Query("hybrid", pattern="^(semantic|fts|hybrid)$"),
) -> list[SearchResult]:
    """Search endpoint with GET (for simple queries)."""
    if mode == "semantic":
        return await repo.search_semantic(
            query=q, top_k=top_k, content_type=content_type, tags=tags
        )
    elif mode == "fts":
        return await repo.search_fts(
            query=q, limit=top_k, content_type=content_type, tags=tags
        )
    else:
        return await repo.search_hybrid(
            query=q, top_k=top_k, content_type=content_type, tags=tags
        )
