"""
TEMPORARY Mode D Indic Parler Mixed TTS test route —
POST /api/v1/test/indic-parler-mixed-tts

Purpose
-------
Isolated manual test endpoint for Mode D: a single-model multilingual TTS experiment
that sends the ORIGINAL Tamil + English mixed text directly to the NEW
ai4bharat/indic-parler-tts model — with NO transliteration, NO eSpeak, NO IndicXlit,
NO segmentation, NO Mode A/B/C logic.

Model used
----------
ai4bharat/indic-parler-tts  (SEPARATE from all existing TTS endpoints)

This is a fine-tuned multilingual extension of Parler-TTS Mini trained on 1,806 hours
of Indic + English data. It uses a description-conditioned voice (Tamil speaker "Jaya")
and accepts mixed Tamil+English text in ONE inference pass.

CRITICAL differences from existing modes:
  - Mode A: segments text, calls IndicF5 + Parler Mini v1 separately, stitches audio
  - Mode B: phonetic normalization, calls IndicF5 only
  - Mode C: sends raw text to IndicF5 directly
  - Mode D (THIS): sends raw text to ai4bharat/indic-parler-tts (different model)

Mode D flow
-----------
Original Tamil + English mixed text
        |
   NO transliteration
   NO eSpeak
   NO IndicXlit
   NO Tamil/English segmentation
   NO dual-model audio join
   NOT IndicF5
   NOT Parler-TTS Mini v1
        |
   ONE call to ai4bharat/indic-parler-tts (call_indic_parler_mixed_tts_direct)
        |
   ONE speaker identity (Jaya — recommended Tamil female, description-conditioned)
        |
   ONE continuous WAV (44,100 Hz)

Isolation guarantee
-------------------
- NEVER called by the existing RAG answer flow.
- Does NOT touch ASR, RAG, ChromaDB, BGE-M3, or any production endpoint.
- Does NOT modify Mode A, Mode B, or Mode C in any way.
- Does NOT use or change MODAL_TAMIL_TTS_URL or MODAL_ENGLISH_TTS_URL.
- Uses its own exclusive URL: MODAL_INDIC_PARLER_MIXED_TTS_URL.
- Gated by USE_INDIC_PARLER_MIXED_TTS_TEST=true (default: false).
- Failure in this route ONLY affects the Mode D test panel.

Development response headers (NOT exposed in production endpoints)
------------------------------------------------------------------
  X-TTS-Engine        : Indic-Parler-TTS
  X-TTS-Mode          : mode-d
  X-TTS-Latency-Ms    : <integer ms>
  X-TTS-Sample-Rate   : 44100
  X-TTS-Speaker       : Jaya

Removal instructions
--------------------
  1. Delete this file.
  2. Remove the two TEMPORARY-marked lines in main_stt.py that register this router.
  3. Remove use_indic_parler_mixed_tts_test and modal_indic_parler_mixed_tts_url
     from config.py and .env.
  4. Remove call_indic_parler_mixed_tts_direct from modal_client.py.
  Nothing else needs to change. Mode A, Mode B, Mode C, Tamil TTS, English TTS,
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
router = APIRouter(prefix="/test", tags=["[TEMP] Mode D Indic Parler Mixed TTS Test"])


class _IndicParlerMixedTTSTestRequest(BaseModel):
    text: str


@router.post("/indic-parler-mixed-tts")
async def test_indic_parler_mixed_tts(req: _IndicParlerMixedTTSTestRequest):
    """
    TEMPORARY Mode D — Synthesize raw Tamil + English mixed text via ONE
    ai4bharat/indic-parler-tts call.

    Request:  { "text": "Artificial Intelligence பயன்படுத்தி difficult topics-ஐ simple ஆக explain பண்ணலாம்." }
    Response: audio/wav bytes (browser-playable, 44100 Hz)

    Mode D rules (strictly enforced):
    - NO transliteration before sending
    - NO eSpeak
    - NO IndicXlit
    - NO Tamil/English segmentation
    - NO IndicF5 + Parler split
    - NOT the same IndicF5 as Mode A/B/C
    - NOT Parler-TTS Mini v1
    - ONE ai4bharat/indic-parler-tts call with the original text
    - ONE speaker (Jaya — description-conditioned Tamil female)

    HTTP 503 if USE_INDIC_PARLER_MIXED_TTS_TEST=false.
    HTTP 422 if text is empty.
    HTTP 400 if MODAL_INDIC_PARLER_MIXED_TTS_URL is not configured.
    HTTP 503 if synthesis fails (model returned no audio).

    Development headers (X-TTS-*) are ONLY present on this test route.
    They are never added to the production /api/v1/voice/tts endpoint.

    This route ONLY calls call_indic_parler_mixed_tts_direct().  It never touches
    ASR, RAG, BGE-M3, ChromaDB, the reranker, Gemma, the localizer, Mode A,
    Mode B, Mode C, or any production TTS path.
    """
    settings = get_settings()

    # ── Gate: disabled unless USE_INDIC_PARLER_MIXED_TTS_TEST=true ───────────
    if not settings.use_indic_parler_mixed_tts_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Mode D Indic Parler Mixed TTS test endpoint is disabled. "
                "Set USE_INDIC_PARLER_MIXED_TTS_TEST=true in .env and restart the server."
            ),
        )

    # ── Validate input ────────────────────────────────────────────────────────
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    # ── Endpoint URL check (fail early with clear message) ────────────────────
    if not settings.modal_indic_parler_mixed_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_INDIC_PARLER_MIXED_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/indic_parler_mixed_tts.py first: "
                "  modal deploy backend/modal_endpoints/indic_parler_mixed_tts.py "
                "Then copy the URL into MODAL_INDIC_PARLER_MIXED_TTS_URL in .env. "
                "Do NOT use MODAL_TAMIL_TTS_URL or MODAL_ENGLISH_TTS_URL for Mode D."
            ),
        )

    logger.info(
        "[TEMP MODE-D TEST] %d chars | text='%s%s'",
        len(text),
        text[:80],
        "..." if len(text) > 80 else "",
    )

    # ── Mode D synthesis: raw text -> ONE indic-parler-tts call, NO preprocessing ──
    from app.services.modal_client import call_indic_parler_mixed_tts_direct

    _t0 = time.perf_counter()
    audio_bytes = await call_indic_parler_mixed_tts_direct(text)
    elapsed_ms = int((time.perf_counter() - _t0) * 1000)

    logger.info("[TIMING] mode_d_test_request: %dms | %d chars", elapsed_ms, len(text))

    if audio_bytes is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Mode D synthesis failed — ai4bharat/indic-parler-tts returned no audio. "
                f"Input: {len(text)} chars. "
                "Check Modal logs: modal logs voicelearn-indic-parler-mixed-tts. "
                "The container may be cold-starting (~90-120 s for first request). "
                "Mode A, Mode B, Mode C, Tamil TTS, English TTS, and RAG are unaffected."
            ),
        )

    # ── Development-only response headers ────────────────────────────────────
    # These are ONLY present on this test route — never on production endpoints.
    headers = {
        "X-TTS-Engine": "Indic-Parler-TTS",
        "X-TTS-Mode": "mode-d",
        "X-TTS-Latency-Ms": str(elapsed_ms),
        "X-TTS-Sample-Rate": "44100",
        "X-TTS-Speaker": "Jaya",
    }

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers=headers,
    )
