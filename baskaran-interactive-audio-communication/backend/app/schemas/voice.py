"""Pydantic schemas for voice/STT endpoints."""

from enum import StrEnum

from pydantic import BaseModel, Field


class Language(StrEnum):
    ENGLISH = "english"
    TAMIL = "tamil"
    SINHALA = "sinhala"
    MIXED = "mixed"  # Thanglish / Singlish


class TranscribeResponse(BaseModel):
    transcript: str = Field(..., description="Whisper transcription of the audio")
    detected_language: str = Field(..., description="ISO language code detected by Whisper")
    selected_language: Language = Field(..., description="Language mode chosen by the user")
    duration_ms: int = Field(..., description="Audio duration in milliseconds")


class VoiceQueryRequest(BaseModel):
    """Used for text-based query when audio is pre-transcribed."""
    transcript: str
    language: Language = Language.ENGLISH
    session_id: str | None = None
