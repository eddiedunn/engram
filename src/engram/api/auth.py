"""Optional bearer-key check for the /api/v1 routes (see Settings.api_keys)."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from engram.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """Allow the request if no keys are configured, or if it carries one of them."""
    keys = get_settings().api_keys
    if not keys:
        return
    if credentials is not None:
        given = credentials.credentials.encode()
        if any(secrets.compare_digest(given, key.encode()) for key in keys):
            return
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
