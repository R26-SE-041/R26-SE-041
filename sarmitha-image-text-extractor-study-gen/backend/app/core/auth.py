"""Validate each protected request with Supabase Auth; never trust decoded claims alone."""

from dataclasses import dataclass, field
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.http import SSL_CONTEXT

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    display_name: str
    access_token: str = field(repr=False)


def auth_configured() -> bool:
    return (
        settings.storage_backend == "supabase"
        and settings.supabase_url.startswith("https://")
        and bool(settings.supabase_publishable_key.get_secret_value())
    )


def user_client(token: str = "") -> httpx.AsyncClient:
    if not auth_configured():
        raise HTTPException(status_code=503, detail="Account services are not configured.")
    headers = {"apikey": settings.supabase_publishable_key.get_secret_value()}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(
        base_url=settings.supabase_url.rstrip("/"), headers=headers,
        timeout=30.0, verify=SSL_CONTEXT,
    )


async def verify_user(token: str) -> AuthUser:
    try:
        async with user_client(token) as client:
            response = await client.get("/auth/v1/user")
        if response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Please sign in again.")
        response.raise_for_status()
        data = response.json()
        user_id = str(UUID(data["id"]))
        return AuthUser(user_id, data.get("email", ""), data.get("user_metadata", {}).get("display_name", ""), token)
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(status_code=503, detail="Account verification is temporarily unavailable.")


async def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> AuthUser:
    if not auth_configured():
        raise HTTPException(status_code=503, detail="Account services are not configured.")
    if credentials is None:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return await verify_user(credentials.credentials)


async def pipeline_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> AuthUser | None:
    # The existing standalone local mode remains usable until Supabase is provisioned.
    if settings.storage_backend == "local":
        return None
    return await require_user(credentials)
