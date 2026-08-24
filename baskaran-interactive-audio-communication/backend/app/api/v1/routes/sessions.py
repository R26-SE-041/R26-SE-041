"""Session routes — create and retrieve Q&A sessions."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db.supabase import get_supabase
from app.schemas.session import SessionResponse
from app.schemas.voice import Language

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/", status_code=201)
async def create_session(
    language: Language = Language.ENGLISH,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    """Create a new Q&A session."""
    session_id = str(uuid.uuid4())
    client = await get_supabase()
    await client.table("sessions").insert({
        "id": session_id,
        "user_id": current_user["sub"],
        "language": language.value,
    }).execute()
    return {"session_id": session_id, "language": language}


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Retrieve session history."""
    client = await get_supabase()
    result = await client.table("sessions").select("*").eq("id", session_id).eq("user_id", current_user["sub"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    row = result.data
    return SessionResponse(
        session_id=uuid.UUID(row["id"]),
        language=Language(row["language"]),
        messages=[],
        created_at=row["created_at"],
    )
