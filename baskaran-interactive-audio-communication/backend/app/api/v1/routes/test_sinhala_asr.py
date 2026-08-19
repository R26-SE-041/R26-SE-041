"""
TEMPORARY Sinhala ASR test route -- POST /api/v1/test/sinhala-asr

Purpose:
    Isolated development endpoint to test the Lingalingeswaran/whisper-small-sinhala
    checkpoint directly.  Accepts an uploaded audio file and returns the raw
    Sinhala Unicode transcript -- NO RAG, NO TTS, NO transcript correction.

Isolation guarantee:
    - This route is NEVER called by the existing ASR/RAG/TTS pipeline.
    - It does NOT touch /api/v1/voice/*, /api/v1/documents/*, or any agent.
    - It is gated by USE_SINHALA_ASR_TEST=true (default: false).
    - It uses its own dedicated Modal endpoint (MODAL_SINHALA_ASR_URL).
    - Failure here ONLY affects this route.

Route:
    POST /api/v1/test/sinhala-asr  -> JSON {"transcript": "...", "latency_ms": int}

Removal:
    1. Delete this file.
    2. Remove the TEMPORARY-marked lines in main_stt.py.
    3. Remove use_sinhala_asr_test and modal_sinhala_asr_url from config.py and .env.
"""

import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Dedicated router -- prefix is /test (the /api/v1 prefix is added in main_stt.py)
router = APIRouter(prefix="/test", tags=["[TEMP] Sinhala ASR Test"])

# Audio content types accepted by this route.
# Passed through to the Modal endpoint unchanged -- preprocessing is done there.
_ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/webm",
    "audio/ogg",
    "application/octet-stream",   # some browsers report this for .wav uploads
}


@router.post("/sinhala-asr")
async def test_sinhala_asr(audio_file: UploadFile = File(...)):
    """
    TEMPORARY -- Transcribe Sinhala audio using whisper-small-sinhala.

    Input:  multipart/form-data, field=audio_file (WAV / MP3 / M4A / WebM)
    Output: {"transcript": "...", "latency_ms": int}

    HTTP 503 if USE_SINHALA_ASR_TEST=false (route disabled).
    HTTP 400 if audio_file is missing or MODAL_SINHALA_ASR_URL is not set.
    HTTP 422 if audio_file is empty.

    This route ONLY calls call_sinhala_asr_direct().
    It NEVER touches: Tamil ASR, English ASR, RAG, BGE-M3, ChromaDB,
    reranker, Gemma, localizer, Tamil TTS, English TTS, Sinhala TTS,
    Mixed TTS, or any production route.
    """
    settings = get_settings()

    # -- Gate: disabled unless USE_SINHALA_ASR_TEST=true -------------------
    if not settings.use_sinhala_asr_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sinhala ASR test endpoint is disabled. "
                "Set USE_SINHALA_ASR_TEST=true in .env and restart the server."
            ),
        )

    # -- URL check ---------------------------------------------------------
    if not settings.modal_sinhala_asr_url.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "MODAL_SINHALA_ASR_URL is not configured. "
                "Deploy backend/modal_endpoints/sinhala_whisper_asr.py first, "
                "then set MODAL_SINHALA_ASR_URL in .env."
            ),
        )

    # -- Validate file -----------------------------------------------------
    if audio_file is None:
        raise HTTPException(status_code=400, detail="audio_file is required.")

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="audio_file is empty.")

    content_type = audio_file.content_type or "application/octet-stream"
    filename = audio_file.filename or "recording.webm"

    logger.info(
        "[TEMP SINHALA ASR TEST] Received %d bytes | file='%s' | type='%s'",
        len(audio_bytes), filename, content_type,
    )

    _t0 = time.perf_counter()

    from app.services.modal_client import call_sinhala_asr_direct

    result = await call_sinhala_asr_direct(
        audio_bytes=audio_bytes,
        filename=filename,
        content_type=content_type,
    )

    elapsed = time.perf_counter() - _t0

    logger.info(
        "[TIMING] sinhala_asr_test_request: %.3fs | %d bytes",
        elapsed, len(audio_bytes),
    )

    if result is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sinhala ASR transcription failed or timed out. "
                "The T4 container may be cold-starting (~60-90 s). "
                "Check Modal logs: modal logs voicelearn-sinhala-whisper-asr"
            ),
        )

    transcript = result.get("text", "")
    latency_ms = result.get("latency_ms", int(elapsed * 1000))

    return JSONResponse({
        "transcript": transcript,
        "latency_ms": latency_ms,
    })
