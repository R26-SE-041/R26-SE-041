"""Authenticate with Supabase; enforce ownership before entering any quiz route."""
import os
import httpx
from fastapi import HTTPException, Request


async def authorize_request(request: Request):
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "Please sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(503, "Account service is not configured.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url + "/auth/v1/user", headers={
                "apikey": key, "Authorization": "Bearer " + token,
            })
    except httpx.RequestError:
        raise HTTPException(503, "Account service is temporarily unavailable.")
    if response.status_code in (401, 403):
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    if response.status_code != 200:
        raise HTTPException(503, "Unable to verify your account. Please try again.")
    user = response.json()
    if not user.get("id"):
        raise HTTPException(401, "Invalid account session.")
    request.state.user = user
    session_id = request.path_params.get("session_id")
    if session_id:
        from app.services.db_service import DbService
        db = DbService()
        try:
            session = db.get_session(session_id)
        finally:
            if not db.is_postgres:
                db.conn.close()
        # Do not disclose whether another learner's session exists.
        if not session or session["student_id"] != user["id"]:
            raise HTTPException(404, "Quiz not found.")
        is_bin_operation = request.url.path.endswith(("/restore", "/trash"))
        if session.get("deleted_at") and not is_bin_operation:
            raise HTTPException(404, "This quiz is in your recycle bin. Restore it to continue.")
    return user
