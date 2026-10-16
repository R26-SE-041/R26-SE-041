"""Email/password accounts and private document history backed by Supabase."""

import time
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, SecretStr

from app.core.auth import AuthUser, auth_configured, require_user, user_client
from app.core.config import settings
from app.services.persistence import PersistenceError, record_auth_event, history_image_urls, remove_run_images

router = APIRouter(prefix="/api")


class SignIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class SignUp(SignIn):
    password: SecretStr = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class Refresh(BaseModel):
    refresh_token: SecretStr


def public_user(data: dict) -> dict:
    return {"id": data["id"], "email": data.get("email", ""), "display_name": data.get("user_metadata", {}).get("display_name", "")}


def session_response(data: dict) -> dict:
    if not data.get("access_token"):
        return {"session": None, "message": "Check your email to confirm your account, then sign in."}
    return {"session": {
        "access_token": data["access_token"], "refresh_token": data["refresh_token"],
        "expires_at": data.get("expires_at", int(time.time()) + data.get("expires_in", 3600)),
        "user": public_user(data["user"]),
    }}


async def auth_request(path: str, payload: dict, *, signup: bool = False) -> dict:
    try:
        async with user_client() as client:
            response = await client.post(path, json=payload)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Too many attempts. Please wait before trying again.")
        if response.status_code in (400, 401, 403, 422):
            code = response.json().get("error_code", "")
            if code == "email_not_confirmed":
                detail = "Confirm your email before signing in."
            elif signup:
                detail = "Could not create an account. Check your details or try signing in."
            else:
                detail = "Email or password is incorrect, or the session has expired."
            raise HTTPException(status_code=400 if signup else 401, detail=detail)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Account services are temporarily unavailable.")


@router.get("/auth/config")
async def account_config():
    return {"enabled": auth_configured()}


@router.post("/auth/signup")
async def signup(request: SignUp):
    if not request.display_name.strip():
        raise HTTPException(status_code=400, detail="Enter your name.")
    data = await auth_request(
        "/auth/v1/signup", {"email": request.email.strip(), "password": request.password.get_secret_value(),
        "data": {"display_name": request.display_name.strip()}}, signup=True,
    )
    return session_response(data)


@router.post("/auth/signin")
async def signin(request: SignIn):
    data = await auth_request("/auth/v1/token?grant_type=password", {
        "email": request.email.strip(), "password": request.password.get_secret_value(),
    })
    try:
        await record_auth_event(str(UUID(data["user"]["id"])), "sign_in")
    except (PersistenceError, KeyError, ValueError):
        raise HTTPException(status_code=503, detail="Could not complete sign in. Please try again.")
    return session_response(data)


@router.post("/auth/refresh")
async def refresh(request: Refresh):
    data = await auth_request("/auth/v1/token?grant_type=refresh_token", {"refresh_token": request.refresh_token.get_secret_value()})
    return session_response(data)


@router.get("/auth/me")
async def me(user: AuthUser = Depends(require_user)):
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@router.post("/auth/signout")
async def signout(user: AuthUser = Depends(require_user)):
    try:
        async with user_client(user.access_token) as client:
            response = await client.post("/auth/v1/logout?scope=local")
            response.raise_for_status()
        await record_auth_event(user.id, "sign_out")
    except (httpx.HTTPError, PersistenceError):
        raise HTTPException(status_code=503, detail="Could not complete sign out. Please try again.")
    return {"status": "signed_out"}


async def history_request(user: AuthUser, method: str, *, params: dict, table: str = "ocr_runs") -> list:
    try:
        async with user_client(user.access_token) as client:
            response = await client.request(method, f"/rest/v1/{table}", params=params,
                                            headers={"Prefer": "return=representation"})
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="History is temporarily unavailable.")


@router.get("/account/activity")
async def account_activity(user: AuthUser = Depends(require_user)):
    return {"items": await history_request(user, "GET", table="auth_events", params={
        "user_id": f"eq.{user.id}", "select": "id,event_type,created_at",
        "order": "created_at.desc", "limit": "10",
    })}


@router.get("/history")
async def history(user: AuthUser = Depends(require_user), limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):
    rows = await history_request(user, "GET", params={
        "user_id": f"eq.{user.id}", "select": "id,created_at,filename,extracted_text",
        "order": "created_at.desc,id.desc", "limit": str(limit + 1), "offset": str(offset),
    })
    return {"items": rows[:limit], "has_more": len(rows) > limit}


@router.get("/history/{run_id}")
async def history_detail(run_id: UUID, user: AuthUser = Depends(require_user)):
    rows = await history_request(user, "GET", params={
        "id": f"eq.{run_id}", "user_id": f"eq.{user.id}",
        "select": "id,created_at,filename,extracted_text,extracted_text_ta,extracted_text_en,lines,original_image_path,enhanced_image_path", "limit": "1",
    })
    if not rows:
        raise HTTPException(status_code=404, detail="History item not found.")
    row = rows[0]
    try:
        row.update(await history_image_urls(row, user))
    except (httpx.HTTPError, PersistenceError, ValueError, KeyError):
        # Keep saved text accessible even during a temporary storage outage.
        row["image_error"] = "Saved images are temporarily unavailable. Reopen this document to try again."
    row.pop("original_image_path", None)
    row.pop("enhanced_image_path", None)
    return row


@router.delete("/history/{run_id}")
async def delete_history(run_id: UUID, user: AuthUser = Depends(require_user)):
    owned = await history_request(user, "GET", params={"id": f"eq.{run_id}", "user_id": f"eq.{user.id}", "select": "id", "limit": "1"})
    if not owned:
        raise HTTPException(status_code=404, detail="History item not found.")
    try:
        await remove_run_images(user.id, str(run_id))
    except (httpx.HTTPError, PersistenceError):
        raise HTTPException(status_code=503, detail="Could not delete saved images. Please try again.")
    rows = await history_request(user, "DELETE", params={"id": f"eq.{run_id}", "user_id": f"eq.{user.id}"})
    if not rows:
        raise HTTPException(status_code=404, detail="History item not found.")
    return {"status": "deleted"}
