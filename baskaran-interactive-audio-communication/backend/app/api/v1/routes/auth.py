"""
Auth routes — thin wrappers around Supabase auth.
We delegate all auth logic to Supabase; FastAPI only proxies requests
and normalizes error responses.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.db.supabase import get_supabase
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    client = await get_supabase()
    try:
        response = await client.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {"data": {"full_name": body.full_name}},
        })
        return {"message": "Registration successful. Check your email to confirm.", "user_id": response.user.id}
    except Exception as e:
        logger.error("Registration failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(body: LoginRequest):
    client = await get_supabase()
    try:
        response = await client.auth.sign_in_with_password({"email": body.email, "password": body.password})
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {"id": response.user.id, "email": response.user.email},
        }
    except Exception as e:
        logger.error("Login failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout")
async def logout():
    client = await get_supabase()
    await client.auth.sign_out()
    return {"message": "Logged out"}
