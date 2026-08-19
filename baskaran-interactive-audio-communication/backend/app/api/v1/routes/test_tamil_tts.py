"""
TEMPORARY Tamil TTS test route — POST /api/v1/test/tamil-tts

Purpose:
    Isolated manual test endpoint so developers can type Tamil text and hear
    how the AI4Bharat Indic Parler-TTS model pronounces it — completely
    independent of the ASR/RAG pipeline.

Isolation guarantee:
    - This route is NEVER called by the existing RAG answer flow.
    - It does NOT touch /api/v1/voice/*, /api/v1/documents/*, or any agent.
    - It is gated by USE_TAMIL_TTS_TEST=true (default: false).

Removal:
    1. Delete this file.
    2. Remove the two TEMPORARY-marked lines in router.py (and main_stt.py).
    3. Remove `use_tamil_tts_test` from config.py and .env.
    Nothing else needs to change.
"""

import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Dedicated router — prefix /test keeps it visually separate in OpenAPI docs ─
router = APIRouter(prefix="/test", tags=["[TEMP] Tamil TTS Test"])

# Accepted Tamil test texts shown in logs for quick identification
_EXAMPLE_TEXTS = [
    "நாயின் வரலாறு மிகவும் பழமையானது.",
    "பிரபலமான நாய் இனங்களில் லாப்ரடோர் ரெட்ரீவர்",
    "வணக்கம். இன்று நாம் நாய்களின் வரலாறு",
]


class _TamilTTSTestRequest(BaseModel):
    text: str
    engine: Literal["indic-parler", "mms"] = "indic-parler"


@router.post("/tamil-tts")
async def test_tamil_tts(req: _TamilTTSTestRequest):
    """
    TEMPORARY — Synthesize Tamil text → WAV audio for manual TTS testing.

    Request:  { "text": "நாயின் வரலாறு மிகவும் பழமையானது." }
    Response: audio/wav bytes (browser-playable)

    HTTP 503 if USE_TAMIL_TTS_TEST=false (route disabled).
    HTTP 422 if text is empty.
    HTTP 400 if Tamil TTS is not configured (MODAL_TAMIL_TTS_URL missing).

    This route ONLY calls call_tamil_tts().  It never touches ASR, RAG,
    BGE-M3, ChromaDB, the reranker, Gemma, or the localizer.
    """
    settings = get_settings()

    # ── Gate: disabled unless USE_TAMIL_TTS_TEST=true ────────────────────────
    if not settings.use_tamil_tts_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Tamil TTS test endpoint is disabled. "
                "Set USE_TAMIL_TTS_TEST=true in .env and restart the server."
            ),
        )

    # ── Validate input ────────────────────────────────────────────────────────
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    # ── URL check (fail early with a clear message) ───────────────────────────
    if not settings.modal_tamil_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_TAMIL_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/tamil_parler_tts.py first, "
                "then set MODAL_TAMIL_TTS_URL in .env."
            ),
        )

    logger.info(
        "[TEMP TTS TEST] Synthesizing %d chars: '%s…'",
        len(text),
        text[:40],
    )

    _t0 = time.perf_counter()

    # ── Use call_tamil_tts_direct() to bypass the USE_TAMIL_TTS gate ──────────
    # call_tamil_tts() returns None immediately when USE_TAMIL_TTS=false.
    # During the test period we deliberately keep USE_TAMIL_TTS=false so the
    # production RAG→TTS auto-trigger doesn't fire, but we still need the test
    # route to reach Modal.  call_tamil_tts_direct() always calls the endpoint
    # as long as MODAL_TAMIL_TTS_URL is set.
    if req.engine == "mms":
        from app.services.modal_client import call_tts

        try:
            audio_bytes = await call_tts(text, "tamil")
        except Exception as exc:
            logger.warning("[TEMP TTS TEST] MMS-TTS failed: %s", exc)
            audio_bytes = None
    else:
        from app.services.modal_client import call_tamil_tts_direct

        audio_bytes = await call_tamil_tts_direct(text)

    elapsed = time.perf_counter() - _t0
    logger.info("[TIMING] tamil_tts_test_request: %.3fs | %d chars", elapsed, len(text))

    if audio_bytes is None:
        # call_tamil_tts() returns None on failure (it never raises).
        # Surface a 503 with enough detail for debugging.
        raise HTTPException(
            status_code=503,
            detail=(
                "Tamil TTS synthesis failed or timed out. "
                "The A10G container may be cold-starting (~90-120 s). "
                "Check Modal logs: modal logs voicelearn-tamil-parler-tts"
            ),
        )

    return Response(content=audio_bytes, media_type="audio/wav")
