"""
JWT security utilities.
Supabase issues JWTs signed with HS256 using the project JWT secret.
We verify locally — no round-trip to Supabase on every request.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)  # auto_error=False → returns None instead of 403


def verify_token(token: str) -> dict:
    """Verify a Supabase JWT and return its payload."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict | None:
    """FastAPI dependency — resolves the authenticated user payload.
    Returns None if no token provided (allows optional auth on some endpoints)."""
    if credentials is None:
        return None
    return verify_token(credentials.credentials)
