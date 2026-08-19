"""
TEMPORARY Mixed TTS test route — POST /api/v1/test/mixed-tts

Purpose:
    Isolated manual test endpoint for the mixed Tamil + English TTS orchestrator.
    Developers can type code-switched text and hear the combined IndicF5 +
    Parler-TTS audio — completely independent of the ASR / RAG pipeline.

Isolation guarantee:
    - NEVER called by the existing RAG answer flow.
    - Does NOT touch ASR, RAG, ChromaDB, BGE-M3, or any production endpoint.
    - Gated by USE_MIXED_TTS_TEST=true (default: false).
    - Reuses the same MODAL_TAMIL_TTS_URL and MODAL_ENGLISH_TTS_URL already
      configured for the production Tamil and English TTS endpoints.

Failure policy:
    If any segment fails, the entire synthesis fails (HTTP 503) — we never
    silently return audio with missing words.

The X-Segments response header contains a JSON array of the detected segments
for development debugging (lang labels + text preview).  The frontend must read
this header only; it is NOT part of the audio/wav body.

Removal:
    1. Delete this file.
    2. Remove the two TEMPORARY-marked lines in main_stt.py.
    3. Remove use_mixed_tts_test from config.py and .env.
    Nothing else needs to change.
"""

import base64
import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.mixed_tts import detect_script, segment_mixed_text

logger = get_logger(__name__)

# Dedicated router — prefix /test keeps it visually separate in OpenAPI docs
router = APIRouter(prefix="/test", tags=["[TEMP] Mixed TTS Test"])


class _MixedTTSTestRequest(BaseModel):
    text: str
    # Development-only A/B control. Production mixed TTS always uses matching.
    voice_matching: bool = True
    # Mode A remains the default; Mode B is deliberately test-only.
    mode: str = "a"


@router.post("/mixed-tts")
async def test_mixed_tts(req: _MixedTTSTestRequest):
    """
    TEMPORARY — Synthesize mixed Tamil + English text → one WAV audio.

    Request:  { "text": "Chocolate-ல் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்." }
    Response: audio/wav bytes (browser-playable)
              X-Segments header: JSON array of detected segments for dev debug

    HTTP 503 if USE_MIXED_TTS_TEST=false.
    HTTP 422 if text is empty.
    HTTP 400 if MODAL_TAMIL_TTS_URL or MODAL_ENGLISH_TTS_URL is not configured.
    HTTP 503 if synthesis fails (any segment returned no audio).

    This route ONLY calls synthesize_mixed_tts().  It never touches ASR, RAG,
    BGE-M3, ChromaDB, the reranker, Gemma, or the localizer.
    """
    settings = get_settings()

    # ── Gate: disabled unless USE_MIXED_TTS_TEST=true ────────────────────────
    if not settings.use_mixed_tts_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Mixed TTS test endpoint is disabled. "
                "Set USE_MIXED_TTS_TEST=true in .env and restart the server."
            ),
        )

    # ── Validate input ────────────────────────────────────────────────────────
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    # ── Endpoint URL checks (fail early with clear messages) ──────────────────
    if not settings.modal_tamil_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_TAMIL_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/tamil_parler_tts.py first, "
                "then set MODAL_TAMIL_TTS_URL in .env."
            ),
        )
    if req.mode.lower() not in {"a", "b"}:
        raise HTTPException(status_code=422, detail="'mode' must be 'a' or 'b'.")
    if req.mode.lower() == "a" and not settings.modal_english_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_ENGLISH_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/english_parler_tts.py first, "
                "then set MODAL_ENGLISH_TTS_URL in .env."
            ),
        )

    # ── Pre-compute segment preview for debug header ──────────────────────────
    script   = detect_script(text)
    segments = segment_mixed_text(text)

    logger.info(
        "[TEMP MIXED TTS TEST] script=%s | %d segments | text='%s…'",
        script, len(segments), text[:60],
    )
    for i, seg in enumerate(segments):
        logger.info(
            "  [%d] %-2s: '%s%s'",
            i,
            seg["language"].upper(),
            seg["text"][:50],
            "…" if len(seg["text"]) > 50 else "",
        )

    # Compact JSON for X-Segments header (lang labels + text preview)
    segments_header = json.dumps([
        {"lang": s["language"].upper(), "text": s["text"][:80]}
        for s in segments
    ])

    # ── Synthesize ────────────────────────────────────────────────────────────
    _t0 = time.perf_counter()

    from app.services.mixed_tts import synthesize_mixed_phonetic_tts, synthesize_mixed_tts
    mode = req.mode.lower()
    normalized_text = ""
    used_fallback = False
    if mode == "b":
        audio_bytes, normalized_text, used_fallback = await synthesize_mixed_phonetic_tts(
            text, voice_matching=req.voice_matching
        )
    else:
        audio_bytes = await synthesize_mixed_tts(text, voice_matching=req.voice_matching)

    elapsed = time.perf_counter() - _t0
    logger.info("[TIMING] mixed_tts_test_request: %.3fs | %d chars", elapsed, len(text))

    if audio_bytes is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Mixed TTS synthesis failed — one or more segments returned no audio. "
                "Words would be missing, so the entire synthesis was aborted. "
                f"Detected script={script!r}, {len(segments)} segment(s). "
                "Check Modal logs for both endpoints: "
                "modal logs voicelearn-tamil-parler-tts  |  "
                "modal logs voicelearn-english-parler-tts. "
                "The containers may be cold-starting (~60-120 s)."
            ),
        )

    headers = {
        "X-Segments": segments_header,
        "X-TTS-Mode": "a-fallback" if used_fallback else mode,
    }
    if mode == "b":
        # Header avoids altering the original answer/body and is test-only.
        # HTTP headers are Latin-1 only; Tamil preview text must be encoded.
        headers["X-Normalized-Text-B64"] = base64.b64encode(
            normalized_text[:4000].encode("utf-8")
        ).decode("ascii")

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers=headers,
    )
