"""Internal service-to-service authentication helpers."""
from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException


def get_internal_api_token() -> str:
    return os.getenv("INTERNAL_API_TOKEN", "").strip()


async def verify_internal_api_token(x_internal_token: str | None = Header(default=None)) -> None:
    expected = get_internal_api_token()
    if not expected:
        raise HTTPException(status_code=503, detail="Internal API token is not configured")

    provided = (x_internal_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid internal API token")
