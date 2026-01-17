"""CLI entry point for Engram server."""

import uvicorn

from engram.config import get_settings


def main() -> None:
    """Run the Engram server."""
    settings = get_settings()

    uvicorn.run(
        "engram.api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
