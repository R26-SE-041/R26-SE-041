"""
TEMPORARY Mode C Multilingual TTS test route — POST /api/v1/test/multilingual-tts

Purpose
-------
Isolated manual test endpoint for Mode C: a single-model multilingual TTS experiment
that sends the ORIGINAL Tamil + English mixed text directly to the existing IndicF5
endpoint — with NO transliteration, NO script segmentation, NO Mode A/B logic.

Model used
----------
ai4bharat/IndicF5  (same endpoint as MODAL_TAMIL_TTS_URL)

IndicF5 is built on the F5-TTS flow-matching DiT architecture, trained on 1,417 hours
of multilingual Indic data (Tamil, Hindi, Bengali, and more). Its polyglot zero-shot
architecture allows it to synthesise mixed Tamil+English text in one inference pass,
using the same Tamil female reference voice for both scripts.

Mode C flow
-----------
Original Tamil + English text
        ↓
  NO transliteration
  NO Tamil phonetic conversion
  NO script segmentation
  NO IndicF5 + Parler split
        ↓
  ONE call to IndicF5 (call_multilingual_tts_direct)
        ↓
  ONE speaker identity (TAM_F_HAPPY_00001.wav)
        ↓
  ONE continuous WAV

Isolation guarantee
-------------------
- NEVER called by the existing RAG answer flow.
- Does NOT touch ASR, RAG, ChromaDB, BGE-M3, or any production endpoint.
- Does NOT modify Mode A or Mode B in any way.
- Does NOT change MODAL_TAMIL_TTS_URL (shared read-only).
- Gated by USE_MULTILINGUAL_TTS_TEST=true (default: false).
- Failure in this route ONLY affects the Mode C test panel.

Development response headers (NOT exposed in production endpoints)
------------------------------------------------------------------
  X-TTS-Engine        : IndicF5-MixedDirect
  X-TTS-Language-Mode : mode-c-multilingual
  X-TTS-Latency-Ms    : <integer ms>

Removal instructions
--------------------
  1. Delete this file.
  2. Remove the two TEMPORARY-marked lines in main_stt.py.
  3. Remove use_multilingual_tts_test from config.py and .env.
  4. Remove call_multilingual_tts_direct from modal_client.py.
  Nothing else needs to change. Mode A, Mode B, Tamil TTS, English TTS,
  production routing, RAG, ASR — all completely untouched.
"""

import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Dedicated router — /test prefix keeps it visually separate in OpenAPI docs
router = APIRouter(prefix="/test", tags=["[TEMP] Mode C Multilingual TTS Test"])


class _MultilingualTTSTestRequest(BaseModel):
    text: str


@router.post("/multilingual-tts")
async def test_multilingual_tts(req: _MultilingualTTSTestRequest):
    """
    TEMPORARY Mode C — Synthesize raw Tamil + English mixed text via ONE IndicF5 call.

    Request:  { "text": "Artificial Intelligence பயன்படுத்தி difficult topics-ஐ simple ஆக explain பண்ணலாம்." }
    Response: audio/wav bytes (browser-playable)

    Mode C rules (strictly enforced):
    - NO transliteration before sending
    - NO Tamil phonetic conversion
    - NO script segmentation
    - NO IndicF5 + Parler split
    - ONE IndicF5 call with the original text
    - ONE speaker (TAM_F_HAPPY_00001.wav reference voice)

    HTTP 503 if USE_MULTILINGUAL_TTS_TEST=false.
    HTTP 422 if text is empty.
    HTTP 400 if MODAL_TAMIL_TTS_URL is not configured.
    HTTP 503 if synthesis fails (IndicF5 returned no audio).

    Development headers (X-TTS-*) are ONLY present on this test route.
    They are never added to the production /api/v1/voice/tts endpoint.

    This route ONLY calls call_multilingual_tts_direct().  It never touches
    ASR, RAG, BGE-M3, ChromaDB, the reranker, Gemma, the localizer, or any
    Mode A / Mode B code path.
    """
    settings = get_settings()

    # ── Gate: disabled unless USE_MULTILINGUAL_TTS_TEST=true ─────────────────
    if not settings.use_multilingual_tts_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Mode C multilingual TTS test endpoint is disabled. "
                "Set USE_MULTILINGUAL_TTS_TEST=true in .env and restart the server."
            ),
        )

    # ── Validate input ────────────────────────────────────────────────────────
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    # ── Endpoint URL check (fail early with clear message) ────────────────────
    if not settings.modal_tamil_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_TAMIL_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/tamil_parler_tts.py first, "
                "then set MODAL_TAMIL_TTS_URL in .env. "
                "Mode C reuses the same IndicF5 endpoint as the Tamil TTS service."
            ),
        )

    logger.info(
        "[TEMP MODE-C TEST] %d chars | text='%s%s'",
        len(text),
        text[:80],
        "…" if len(text) > 80 else "",
    )

    # ── Mode C synthesis: raw text → ONE IndicF5 call, NO preprocessing ──────
    from app.services.modal_client import call_multilingual_tts_direct

    _t0 = time.perf_counter()
    audio_bytes = await call_multilingual_tts_direct(text)
    elapsed_ms = int((time.perf_counter() - _t0) * 1000)

    logger.info("[TIMING] mode_c_test_request: %dms | %d chars", elapsed_ms, len(text))

    if audio_bytes is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Mode C synthesis failed — IndicF5 returned no audio. "
                f"Input: {len(text)} chars. "
                "Check Modal logs: modal logs voicelearn-tamil-parler-tts. "
                "The container may be cold-starting (~90-120 s). "
                "Mode A, Mode B, Tamil TTS, English TTS, and RAG are unaffected."
            ),
        )

    # ── Development-only response headers ────────────────────────────────────
    # These are ONLY present on this test route — never on production endpoints.
    headers = {
        "X-TTS-Engine": "IndicF5-MixedDirect",
        "X-TTS-Language-Mode": "mode-c-multilingual",
        "X-TTS-Latency-Ms": str(elapsed_ms),
    }

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers=headers,
    )
