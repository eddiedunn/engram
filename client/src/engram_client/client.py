"""Engram HTTP client."""

from typing import Any

import httpx

from engram_client.models import Content, ContentType, SearchResult, StoreResponse


class EngramClientError(Exception):
    """Error from Engram client operations."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class EngramClient:
    """HTTP client for Engram corpus service.

    This is a thin client with minimal dependencies (no ML libraries).
    All heavy lifting (chunking, embedding) is done server-side.

    Example:
        client = EngramClient("http://localhost:8800")

        # Store content
        result = client.store(
            content_id="video_123",
            content_type="youtube",
            title="Introduction to ML",
            text="In this video we explore...",
            tags=["ai", "tutorial"]
        )

        # Search
        results = client.search("neural networks", top_k=5)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8800",
        timeout: float = 60.0,
    ):
        """Initialize client.

        Args:
            base_url: Engram server URL
            timeout: Request timeout in seconds (embedding can take time)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=f"{self.base_url}/api/v1",
            timeout=timeout,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "EngramClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle HTTP response and raise on errors."""
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise EngramClientError(detail, response.status_code)
        return response.json()

    def health(self) -> dict:
        """Check server health."""
        response = self._client.get(f"{self.base_url}/health")
        return self._handle_response(response)

    def store(
        self,
        content_id: str,
        content_type: str | ContentType,
        title: str,
        text: str,
        url: str | None = None,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> StoreResponse:
        """Store content in the corpus.

        Args:
            content_id: Unique external identifier
            content_type: Type of content (youtube, article, etc.)
            title: Content title
            text: Full text content
            url: Optional source URL
            summary: Optional pre-computed summary
            metadata: Optional metadata dict
            tags: Optional list of tags

        Returns:
            StoreResponse with ID and chunk count
        """
        payload = {
            "content_id": content_id,
            "content_type": str(content_type),
            "title": title,
            "text": text,
            "url": url,
            "summary": summary,
            "metadata": metadata or {},
            "tags": tags or [],
        }
        response = self._client.post("/content", json=payload)
        data = self._handle_response(response)
        return StoreResponse(**data)

    def get(self, content_id: str) -> Content | None:
        """Get content by external ID.

        Args:
            content_id: External content identifier

        Returns:
            Content if found, None otherwise
        """
        try:
            response = self._client.get(f"/content/{content_id}")
            data = self._handle_response(response)
            return Content(**data)
        except EngramClientError as e:
            if e.status_code == 404:
                return None
            raise

    def delete(self, content_id: str) -> bool:
        """Delete content by external ID.

        Args:
            content_id: External content identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            response = self._client.delete(f"/content/{content_id}")
            self._handle_response(response)
            return True
        except EngramClientError as e:
            if e.status_code == 404:
                return False
            raise

    def list(
        self,
        content_type: str | ContentType | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Content]:
        """List content with optional filters.

        Args:
            content_type: Filter by content type
            tags: Filter by tags (any match)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of Content objects
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if content_type:
            params["content_type"] = str(content_type)
        if tags:
            params["tags"] = tags

        response = self._client.get("/content", params=params)
        data = self._handle_response(response)
        return [Content(**item) for item in data]

    def search(
        self,
        query: str,
        top_k: int = 10,
        content_type: str | ContentType | None = None,
        tags: list[str] | None = None,
        mode: str = "hybrid",
    ) -> list[SearchResult]:
        """Search the corpus.

        Args:
            query: Search query
            top_k: Maximum results
            content_type: Filter by content type
            tags: Filter by tags
            mode: Search mode - "semantic", "fts", or "hybrid"

        Returns:
            List of SearchResult objects
        """
        params: dict[str, Any] = {
            "q": query,
            "top_k": top_k,
            "mode": mode,
        }
        if content_type:
            params["content_type"] = str(content_type)
        if tags:
            params["tags"] = tags

        response = self._client.get("/search", params=params)
        data = self._handle_response(response)
        return [SearchResult(**item) for item in data]

    def search_semantic(
        self,
        query: str,
        top_k: int = 10,
        content_type: str | ContentType | None = None,
        tags: list[str] | None = None,
        threshold: float = 0.0,
    ) -> list[SearchResult]:
        """Semantic search using vector similarity.

        Args:
            query: Natural language query
            top_k: Maximum results
            content_type: Filter by content type
            tags: Filter by tags
            threshold: Minimum similarity score (0-1)

        Returns:
            List of SearchResult objects
        """
        payload = {
            "query": query,
            "top_k": top_k,
            "content_type": str(content_type) if content_type else None,
            "tags": tags,
            "threshold": threshold,
        }
        response = self._client.post("/search/semantic", json=payload)
        data = self._handle_response(response)
        return [SearchResult(**item) for item in data]

    def search_hybrid(
        self,
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.7,
        content_type: str | ContentType | None = None,
        tags: list[str] | None = None,
    ) -> list[SearchResult]:
        """Hybrid search combining semantic and full-text.

        Args:
            query: Search query
            top_k: Maximum results
            semantic_weight: Weight for semantic (0-1), FTS gets remainder
            content_type: Filter by content type
            tags: Filter by tags

        Returns:
            List of SearchResult objects
        """
        payload = {
            "query": query,
            "top_k": top_k,
            "semantic_weight": semantic_weight,
            "content_type": str(content_type) if content_type else None,
            "tags": tags,
        }
        response = self._client.post("/search/hybrid", json=payload)
        data = self._handle_response(response)
        return [SearchResult(**item) for item in data]
