"""Authentication helpers and role-based access dependencies."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, ExpiredSignatureError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_control_db
from app.services.account import account_service, has_any_role

auth_scheme = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "12"))


def get_auth_secret() -> str:
    """Return the signing secret used for bearer tokens."""
    return (
        os.getenv("APP_SECRET_KEY", "").strip()
        or os.getenv("SECRET_KEY", "").strip()
        or os.getenv("INTERNAL_API_TOKEN", "").strip()
        or "hbbwater-dev-secret"
    )


def create_access_token(user: dict[str, Any]) -> tuple[str, int]:
    """Create a signed access token for a serialized user profile."""
    expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    expires_at = datetime.utcnow() + expires_delta
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "type": "access",
        "exp": expires_at,
    }
    token = jwt.encode(payload, get_auth_secret(), algorithm=JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: AsyncSession = Depends(get_control_db),
) -> dict[str, Any]:
    """Return the authenticated user profile represented by a bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("请先登录")

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_auth_secret(),
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(payload.get("sub", 0))
        if payload.get("type") != "access" or user_id <= 0:
            raise _unauthorized("登录状态无效，请重新登录")
    except ExpiredSignatureError as exc:
        raise _unauthorized("登录已过期，请重新登录") from exc
    except (JWTError, TypeError, ValueError) as exc:
        raise _unauthorized("登录状态无效，请重新登录") from exc

    try:
        return await account_service.get_profile(db, user_id=user_id)
    except HTTPException as exc:
        raise _unauthorized("登录状态无效，请重新登录") from exc


def require_roles(*roles: str) -> Callable[..., Any]:
    """Create a dependency that restricts access to one or more roles."""

    async def dependency(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not has_any_role(current_user.get("role"), roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前账号无权访问此功能",
            )
        return current_user

    return dependency
