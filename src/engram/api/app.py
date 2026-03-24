"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engram.api.routes import router
from engram.config import get_settings
from engram.db.connection import close_db, init_db
from engram.embedding import Embedder

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()
    logger.info("Starting Engram", version="0.1.0", port=settings.api_port)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    yield

    # Cleanup
    await close_db()
    logger.info("Engram shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Engram",
        description="Knowledge corpus service with vector search",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint."""
        embedder = Embedder()
        embed_healthy = await embedder.check_health()

        overall_status = "healthy" if embed_healthy else "degraded"

        return {
            "status": overall_status,
            "version": "0.1.0",
            "services": {
                "embed": "healthy" if embed_healthy else "unavailable"
            }
        }

    return app
