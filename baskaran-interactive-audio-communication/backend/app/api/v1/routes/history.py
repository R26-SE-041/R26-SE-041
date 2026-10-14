"""Persistent, user-scoped Q&A history endpoints."""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.history_store import attach_audio, create_history, get_audio_path, list_history, delete_history, update_answer

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
    question_audio: Annotated[UploadFile | None, File()] = None,
    document_grounded: Annotated[bool, Form()] = True,
    source_id: Annotated[str | None, Form(max_length=100)] = None,
    created_at: Annotated[datetime | None, Form()] = None,
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    try:
        parsed_references = json.loads(references)
        if not isinstance(parsed_references, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="references must be a JSON array")
    user_id = _user_id(current_user)
    if language not in {'english', 'tamil', 'sinhala'} or not question.strip() or not answer.strip():
        raise HTTPException(422, 'Question, answer and a supported language are required')
    audio = await _read_audio(audio_file)
    question_content = await _read_audio(question_audio)
    return create_history(user_id, question.strip(), answer.strip(), language,
                          parsed_references, audio, question_content, document_grounded,
                          source_id, created_at.isoformat() if created_at else None)


@router.put("/{history_id}/audio")
async def history_attach_audio(
    history_id: str, audio_file: Annotated[UploadFile, File()],
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    audio = await _read_audio(audio_file)
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


async def _read_audio(file):
    if file is None:
        return None
    data = await file.read(50 * 1024 * 1024 + 1)
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(413, 'Audio exceeds the 50 MB limit')
    return data


@router.get('/{history_id}/question-audio')
def question_audio(history_id: str, current_user: Annotated[dict | None, Depends(get_current_user)]):
    path = get_audio_path(_user_id(current_user), history_id, 'question')
    if not path:
        raise HTTPException(404, 'Audio not found')
    with path.open('rb') as audio:
        magic = audio.read(16)
    mime = 'audio/wav' if magic.startswith(b'RIFF') else 'audio/webm' if magic.startswith(b'\x1aE\xdf\xa3') else 'audio/mp4' if b'ftyp' in magic else 'application/octet-stream'
    return FileResponse(path, media_type=mime)


class AnswerEdit(BaseModel):
    answer: str


@router.patch('/{history_id}')
def edit_history(history_id: str, body: AnswerEdit, current_user: Annotated[dict | None, Depends(get_current_user)]):
    if not body.answer.strip():
        raise HTTPException(422, 'Answer cannot be empty')
    item = update_answer(_user_id(current_user), history_id, body.answer.strip())
    if not item:
        raise HTTPException(404, 'History item not found')
    return item


class DeleteHistory(BaseModel):
    confirmed: bool = False


@router.delete('')
def clear_history(body: DeleteHistory, current_user: Annotated[dict | None, Depends(get_current_user)]):
    if not body.confirmed:
        raise HTTPException(409, 'Confirm deleting your cloud history')
    delete_history(_user_id(current_user))
    return {'deleted': True}


@router.delete('/{history_id}')
def remove_history(history_id: str, body: DeleteHistory, current_user: Annotated[dict | None, Depends(get_current_user)]):
    if not body.confirmed:
        raise HTTPException(409, 'Confirm deleting this history item')
    if not delete_history(_user_id(current_user), history_id):
        raise HTTPException(404, 'History item not found')
    return {'deleted': True}
