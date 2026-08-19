"""
TEMPORARY English TTS test route — POST /api/v1/test/english-tts

Purpose:
    Isolated manual test endpoint so developers can type English text
    (and optionally a voice style description) and hear how Parler-TTS
    Mini v1 pronounces it — completely independent of the ASR/RAG pipeline.

Isolation guarantee:
    - This route is NEVER called by the existing RAG answer flow.
    - It does NOT touch /api/v1/voice/*, /api/v1/documents/*, or any agent.
    - It is gated by USE_ENGLISH_TTS_TEST=true (default: false).
    - It uses the SAME deployed Modal endpoint as the production feature.

Removal:
    1. Delete this file.
    2. Remove the two TEMPORARY-marked lines in main_stt.py.
    3. Remove `use_english_tts_test` from config.py and .env.
    Nothing else needs to change.
"""

import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Dedicated router — prefix /test keeps it visually separate in OpenAPI docs ─
router = APIRouter(prefix="/test", tags=["[TEMP] English TTS Test"])


class _EnglishTTSTestRequest(BaseModel):
    text: str
    description: str = ""


@router.post("/english-tts")
async def test_english_tts(req: _EnglishTTSTestRequest):
    """
    TEMPORARY — Synthesize English text → WAV audio for manual TTS testing.

    Request:  { "text": "AI helps students learn.", "description": "(optional style)" }
    Response: audio/wav bytes (browser-playable)

    HTTP 503 if USE_ENGLISH_TTS_TEST=false (route disabled).
    HTTP 422 if text is empty.
    HTTP 400 if English TTS is not configured (MODAL_ENGLISH_TTS_URL missing).

    This route ONLY calls call_english_tts_direct().  It never touches ASR, RAG,
    BGE-M3, ChromaDB, the reranker, Gemma, the localizer, or Tamil TTS.
    """
    settings = get_settings()

    # ── Gate: disabled unless USE_ENGLISH_TTS_TEST=true ─────────────────────
    if not settings.use_english_tts_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "English TTS test endpoint is disabled. "
                "Set USE_ENGLISH_TTS_TEST=true in .env and restart the server."
            ),
        )

    # ── Validate input ────────────────────────────────────────────────────────
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    # ── URL check (fail early with a clear message) ───────────────────────────
    if not settings.modal_english_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_ENGLISH_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/english_parler_tts.py first, "
                "then set MODAL_ENGLISH_TTS_URL in .env."
            ),
        )

    description = (req.description or "").strip()

    logger.info(
        "[TEMP ENGLISH TTS TEST] Synthesizing %d chars: '%s…' | description: '%s…'",
        len(text),
        text[:40],
        description[:40] if description else "(default)",
    )

    _t0 = time.perf_counter()

    # ── Use call_english_tts_direct() to bypass the USE_ENGLISH_TTS gate ─────
    # call_english_tts() returns None immediately when USE_ENGLISH_TTS=false.
    # During the test period we keep USE_ENGLISH_TTS=false so the production
    # RAG→TTS auto-trigger doesn't fire, but we still need the test route to
    # reach Modal.  call_english_tts_direct() always calls the endpoint as long
    # as MODAL_ENGLISH_TTS_URL is set.
    # Important: call_english_tts_direct() does NOT bypass error handling,
    # timeout, URL config, or response validation — only the feature flag.
    from app.services.modal_client import call_english_tts_direct

    audio_bytes = await call_english_tts_direct(text, description)

    elapsed = time.perf_counter() - _t0
    logger.info(
        "[TIMING] english_tts_test_request: %.3fs | %d chars",
        elapsed, len(text),
    )

    if audio_bytes is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "English TTS synthesis failed or timed out. "
                "The T4 container may be cold-starting (~60-90 s). "
                "Check Modal logs: modal logs voicelearn-english-parler-tts"
            ),
        )

    return Response(content=audio_bytes, media_type="audio/wav")
