"""Pydantic schemas for Q&A sessions."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.voice import Language
from app.schemas.document import ChunkReference


class SessionMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    audio_url: str | None = None
    references: list[ChunkReference] = []
    created_at: datetime


class SessionResponse(BaseModel):
    session_id: UUID
    language: Language
    messages: list[SessionMessage] = []
    created_at: datetime


class QueryResponse(BaseModel):
    """Full pipeline response returned to the frontend."""
    session_id: UUID
    transcript: str
    enhanced_query: str | None = None
    answer: str
    audio_url: str | None = None
    language: Language
    references: list[ChunkReference] = []
