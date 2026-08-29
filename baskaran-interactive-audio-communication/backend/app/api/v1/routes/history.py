"""Persistent, user-scoped Q&A history endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.security import get_current_user
from app.services.history_store import attach_audio, create_history, get_audio_path, list_history

router = APIRouter(prefix="/history", tags=["history"])


def _user_id(user: dict | None) -> str:
    if not user or not user.get("sub"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(user["sub"])


@router.get("")
async def history_list(current_user: Annotated[dict | None, Depends(get_current_user)]):
    return list_history(_user_id(current_user))


@router.post("", status_code=201)
async def history_create(
    question: Annotated[str, Form()], answer: Annotated[str, Form()],
    language: Annotated[str, Form()], references: Annotated[str, Form()] = "[]",
    audio_file: Annotated[UploadFile | None, File()] = None,
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    try:
        parsed_references = json.loads(references)
        if not isinstance(parsed_references, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="references must be a JSON array")
    audio = await audio_file.read() if audio_file else None
    return create_history(_user_id(current_user), question.strip(), answer.strip(), language,
                          parsed_references, audio)


@router.put("/{history_id}/audio")
async def history_attach_audio(
    history_id: str, audio_file: Annotated[UploadFile, File()],
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    audio = await audio_file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    item = attach_audio(_user_id(current_user), history_id, audio)
    if not item:
        raise HTTPException(status_code=404, detail="History item not found")
    return item


@router.get("/{history_id}/audio")
async def history_audio(history_id: str,
                        current_user: Annotated[dict | None, Depends(get_current_user)]):
    path = get_audio_path(_user_id(current_user), history_id)
    if not path:
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/wav", filename=f"answer-{history_id}.wav")
