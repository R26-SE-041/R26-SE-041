"""Verify Supabase JWTs locally, with cached JWKS for asymmetric signing keys."""

from typing import Annotated
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)  # auto_error=False → returns None instead of 403

@lru_cache(maxsize=4)
def _jwks(url: str):
    return jwt.PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json", timeout=10)


def verify_token(token: str) -> dict:
    """Verify a Supabase JWT and return its payload."""
    settings = get_settings()
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
        if algorithm not in {"HS256", "ES256", "RS256"}:
            raise jwt.InvalidTokenError("Unsupported signing algorithm")
        key = (settings.supabase_jwt_secret if algorithm == "HS256"
               else _jwks(settings.supabase_url).get_signing_key_from_jwt(token).key)
        payload = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience="authenticated",
            **({"issuer": f"{settings.supabase_url.rstrip('/')}/auth/v1", "options": {"require": ["exp", "sub", "iss"]}}
               if settings.require_auth else {}),
        )
        return payload
    except jwt.PyJWKClientError:
        raise HTTPException(status_code=503, detail="Authentication key service is unavailable.")
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
        if get_settings().require_auth:
            raise HTTPException(status_code=401, detail="Sign in to use VoiceLearn.")
        return None
    return verify_token(credentials.credentials)
