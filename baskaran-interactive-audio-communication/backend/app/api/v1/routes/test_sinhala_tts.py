"""
TEMPORARY Sinhala TTS test route — POST /api/v1/test/sinhala-tts

Purpose:
    Isolated manual test endpoint so developers can type Sinhala text
    and hear how the dialoglk/SinhalaVITS-TTS-F1 model synthesizes it —
    completely independent of the ASR/RAG pipeline.

Isolation guarantee:
    - This route is NEVER called by the existing RAG answer flow.
    - It does NOT touch /api/v1/voice/*, /api/v1/documents/*, or any agent.
    - It is gated by USE_SINHALA_TTS_TEST=true (default: false).
    - It uses its own dedicated Modal endpoint (MODAL_SINHALA_VITS_TTS_URL).
    - Failure here ONLY affects this route — Tamil, English, Mixed TTS,
      ASR, RAG, ChromaDB, BGE-M3, and all other routes are unaffected.

Routes:
    POST /api/v1/test/sinhala-tts           → audio/wav
    POST /api/v1/test/sinhala-tts/romanize  → {"original": ..., "romanized": ...}

Removal:
    1. Delete this file.
    2. Remove the two TEMPORARY-marked lines in router.py.
    3. Remove `use_sinhala_tts_test` and `modal_sinhala_vits_tts_url`
       from config.py and .env.
    Nothing else needs to change.
"""

import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Dedicated router ──────────────────────────────────────────────────────────
router = APIRouter(prefix="/test", tags=["[TEMP] Sinhala TTS Test"])


class _SinhalaTTSTestRequest(BaseModel):
    text: str
    mixed_phonetic_preprocessing: bool = False


class _RomanizeRequest(BaseModel):
    text: str


# ── Synthesis endpoint ────────────────────────────────────────────────────────

@router.post("/sinhala-tts")
async def test_sinhala_tts(req: _SinhalaTTSTestRequest):
    """
    TEMPORARY — Synthesize Sinhala text → WAV audio for manual TTS testing.

    Request:  { "text": "සිංහල භාෂාව ශ්‍රී ලංකාවේ ප්‍රධාන භාෂාවක්." }
    Response: audio/wav bytes (browser-playable, 22,050 Hz)

    HTTP 503 if USE_SINHALA_TTS_TEST=false (route disabled).
    HTTP 422 if text is empty.
    HTTP 400 if MODAL_SINHALA_VITS_TTS_URL is not configured.

    This route ONLY calls call_sinhala_vits_tts_direct().
    It NEVER touches: ASR, RAG, BGE-M3, ChromaDB, reranker, Gemma,
    localizer, Tamil TTS, English TTS, or Mixed TTS.
    """
    settings = get_settings()

    # ── Gate: disabled unless USE_SINHALA_TTS_TEST=true ─────────────────────
    if not settings.use_sinhala_tts_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sinhala TTS test endpoint is disabled. "
                "Set USE_SINHALA_TTS_TEST=true in .env and restart the server."
            ),
        )

    # ── Validate input ────────────────────────────────────────────────────────
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    # ── URL check (fail early with a clear message) ──────────────────────────
    if not settings.modal_sinhala_vits_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_SINHALA_VITS_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/sinhala_vits_tts.py first, "
                "then set MODAL_SINHALA_VITS_TTS_URL in .env."
            ),
        )

    logger.info(
        "[TEMP SINHALA TTS TEST] Synthesizing %d chars: '%s…'",
        len(text),
        text[:40],
    )

    _t0 = time.perf_counter()

    from app.services.modal_client import call_sinhala_vits_tts_direct

    phonetic_text = text
    warnings: list[str] = []
    if req.mixed_phonetic_preprocessing:
        from app.services.sinhala_mixed_phonetics import SinhalaMixedPhonetics
        result = await SinhalaMixedPhonetics(settings.sinhala_phonetics_cache_path).preprocess(text)
        phonetic_text, warnings = result.phonetic_text, result.warnings
    audio_bytes = await call_sinhala_vits_tts_direct(phonetic_text)

    elapsed = time.perf_counter() - _t0
    logger.info(
        "[TIMING] sinhala_tts_test_request: %.3fs | %d chars",
        elapsed, len(text),
    )

    if audio_bytes is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sinhala TTS synthesis failed or timed out. "
                "The T4 container may be cold-starting (~60-90 s). "
                "Check Modal logs: modal logs voicelearn-sinhala-vits-tts"
            ),
        )

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "X-TTS-Engine": "SinhalaVITS-F1",
            "X-TTS-Latency-Ms": str(int(elapsed * 1000)),
            "X-TTS-Sample-Rate": "22050",
            "X-TTS-Phonetic-Preprocessing": str(req.mixed_phonetic_preprocessing).lower(),
            "X-TTS-Phonetic-Warnings": str(len(warnings)),
            "Access-Control-Expose-Headers": (
                "X-TTS-Engine, X-TTS-Latency-Ms, X-TTS-Sample-Rate, X-TTS-Phonetic-Preprocessing, X-TTS-Phonetic-Warnings"
            ),
        },
    )


# ── Romanizer debug endpoint ──────────────────────────────────────────────────

@router.post("/sinhala-tts/romanize")
async def test_sinhala_tts_romanize(req: _RomanizeRequest):
    """
    TEMPORARY — Preview the romanizer output for Sinhala text WITHOUT synthesis.

    Request:  { "text": "සිංහල..." }
    Response: { "original": "...", "romanized": "..." }

    This is purely a debug utility to inspect how:
        - Sinhala Unicode characters are romanized
        - English words embedded in Sinhala are handled (they pass through unchanged)
        - Acronyms and punctuation behave

    This route calls the /romanize endpoint on the Modal container —
    the same romanizer.py that is used during synthesis.

    DO NOT expose in production — remove with the rest of this file.
    """
    settings = get_settings()

    if not settings.use_sinhala_tts_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sinhala TTS test endpoint is disabled. "
                "Set USE_SINHALA_TTS_TEST=true in .env and restart the server."
            ),
        )

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")

    if not settings.modal_sinhala_vits_tts_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_SINHALA_VITS_TTS_URL is not configured. "
                "Deploy backend/modal_endpoints/sinhala_vits_tts.py first."
            ),
        )

    from app.services.modal_client import call_sinhala_vits_romanize

    result = await call_sinhala_vits_romanize(text)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Romanizer call failed or timed out. "
                "Check Modal logs: modal logs voicelearn-sinhala-vits-tts"
            ),
        )
    return result


@router.post("/sinhala-tts/phonetic-preview")
async def test_sinhala_tts_phonetic_preview(req: _SinhalaTTSTestRequest):
    """Development preview only; returns a hidden TTS copy and provenance."""
    settings = get_settings()
    if not settings.use_sinhala_tts_test:
        raise HTTPException(status_code=503, detail="Sinhala TTS test endpoint is disabled.")
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="'text' cannot be empty.")
    from app.services.modal_client import call_sinhala_vits_romanize
    from app.services.sinhala_mixed_phonetics import SinhalaMixedPhonetics
    result = await SinhalaMixedPhonetics(settings.sinhala_phonetics_cache_path).preprocess(text)
    preview = SinhalaMixedPhonetics.as_preview(result)
    romanized = await call_sinhala_vits_romanize(result.phonetic_text)
    preview["romanized"] = romanized.get("romanized") if romanized else None
    return preview
