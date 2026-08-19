"""
Voice API routes.

POST /api/v1/voice/transcribe
    Phase 1 endpoint: accepts audio file + language, returns transcript.
    Uses STT-only LangGraph pipeline.

POST /api/v1/voice/query  (Phase 2 — skeleton)
    Full pipeline: STT → Prompt Enh. → RAG → Localization → TTS.
"""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.agents.orchestrator import build_graph, build_stt_only_graph
from app.core.security import get_current_user
from app.schemas.voice import Language, TranscribeResponse, VoiceQueryRequest
from app.schemas.session import QueryResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_MB = 25
ALLOWED_TYPES = {
    "audio/webm", "audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave", "audio/mpeg", "audio/mp3", "audio/ogg",
    "audio/mp4", "audio/m4a", "audio/x-m4a", "application/octet-stream",
}


class TTSRequest(BaseModel):
    """Text and selected UI language for speech synthesis."""

    text: str
    language: Language


def _validate_audio(file: UploadFile) -> None:
    if not file.content_type:
        return
    # Strip codec suffix e.g. "audio/webm;codecs=opus" → "audio/webm"
    base_type = file.content_type.split(";")[0].strip()
    if base_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type: {file.content_type}",
        )


@router.post("/tts", response_class=Response)
async def text_to_speech(
    request: TTSRequest,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    """Synthesize a localized answer to WAV audio.

    Tamil is routed to AI4Bharat Indic Parler-TTS, a Tamil-specific model.
    MMS-TTS remains in use for English, Sinhala, and mixed text.
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    logger.info(
        "TTS request: user=%s, language=%s, chars=%d",
        current_user.get("sub") if current_user else "anon",
        request.language.value,
        len(text),
    )

    if request.language is Language.TAMIL:
        from app.services.modal_client import call_tamil_tts

        audio_bytes = await call_tamil_tts(text)
        if audio_bytes is None:
            raise HTTPException(
                status_code=503,
                detail="Tamil TTS is currently unavailable. Text answer is still shown.",
            )
    else:
        from app.services.modal_client import call_tts

        try:
            audio_bytes = await call_tts(text, request.language.value)
        except Exception as exc:
            logger.warning("MMS-TTS failed for %s: %s", request.language.value, exc)
            raise HTTPException(status_code=503, detail="TTS service is currently unavailable.") from exc

    return Response(content=audio_bytes, media_type="audio/wav")


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio_file: Annotated[UploadFile, File(description="Audio recording (webm/wav/mp3/m4a/ogg)")],
    language: Annotated[Language, Form(description="Language mode selected by user")] = Language.ENGLISH,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    """
    Phase 1 endpoint — Speech-to-Text only.

    1. Validates audio format and size.
    2. Runs STT-only LangGraph pipeline (Whisper Large V3 on Modal).
    3. Returns transcript + detected language.
    """
    _validate_audio(audio_file)

    audio_bytes = await audio_file.read()

    if len(audio_bytes) > MAX_AUDIO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds {MAX_AUDIO_MB}MB limit",
        )

    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty",
        )

    logger.info(
        "Transcribe request: user=%s, size=%d bytes, language=%s",
        current_user.get("sub") if current_user else "anon",
        len(audio_bytes),
        language,
    )

    start = time.perf_counter()

    graph = build_stt_only_graph()
    result = await graph.ainvoke({
        "audio_bytes": audio_bytes,
        "audio_filename": audio_file.filename or "recording.webm",
        "language": language.value,
    })

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.info("STT completed in %dms", elapsed_ms)

    return TranscribeResponse(
        transcript=result["transcript"],
        detected_language=result.get("detected_language", "en"),
        selected_language=language,
        duration_ms=result.get("duration_ms", 0),
    )


@router.post("/query", response_model=QueryResponse)
async def voice_query(
    audio_file: Annotated[UploadFile, File(description="Audio recording")],
    language: Annotated[Language, Form()] = Language.ENGLISH,
    session_id: Annotated[str | None, Form()] = None,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    """
    Full Phase 2 pipeline: STT → Prompt Enh. → RAG → Localization → TTS.
    Returns transcript, answer, audio URL, and document references.
    """
    _validate_audio(audio_file)
    audio_bytes = await audio_file.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    user_id = current_user.get("sub", "") if current_user else ""

    graph = build_graph()
    result = await graph.ainvoke({
        "audio_bytes": audio_bytes,
        "audio_filename": audio_file.filename or "recording.webm",
        "language": language.value,
        "user_id": user_id,
        "session_id": session_id,
    })

    from uuid import uuid4
    from app.schemas.document import ChunkReference

    references = []
    for chunk in result.get("chunks", []):
        meta = chunk.get("metadata", {})
        references.append(ChunkReference(
            document_id=meta.get("document_id", str(uuid4())),
            filename=meta.get("filename", ""),
            chunk_index=0,
            page=meta.get("page"),
            excerpt=chunk["text"][:200],
            score=chunk.get("score", 0.0),
        ))

    return QueryResponse(
        session_id=session_id or str(uuid4()),
        transcript=result.get("transcript", ""),
        enhanced_query=result.get("enhanced_query"),
        answer=result.get("localized_answer") or result.get("answer", ""),
        audio_url=result.get("audio_url"),
        language=language,
        references=references,
    )
