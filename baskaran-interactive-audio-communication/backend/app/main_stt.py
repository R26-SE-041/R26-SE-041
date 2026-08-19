"""
FastAPI app for Phase 1 + Phase 2 testing.

Includes:
  - /api/v1/voice/transcribe  — Whisper STT (Phase 1)
  - /api/v1/documents/*       — Upload, list, delete, ask/RAG (Phase 2)

Run:
    py -3 -m uvicorn app.main_stt:app --reload --port 8000

Then open: http://localhost:3000/test
"""

import pathlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.bge_m3_cache import bge_m3_cache_status
from app.services.modal_client import call_whisper, call_transcript_corrector, call_rag_generator, call_localizer, call_script_corrector


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = get_logger("startup")
    settings = get_settings()
    logger.info("VoiceLearn Phase1+2 Server | WHISPER=%s", bool(settings.modal_whisper_url))

    # ── Pre-warm ML models in the background ────────────────────────────────
    # BGE-M3 weights are ~1.2 GB and take 60-90 s to load on CPU.
    # Starting the load NOW (at startup) means the first user "Ask" request
    # finds the model already in memory instead of timing out.
    # asyncio.create_task keeps startup non-blocking.
    async def _warmup_models():
        import asyncio as _asyncio
        from app.services.bge_m3_cache import bge_m3_cache_status

        # When Modal GPU mode is active, the local BGE-M3 and reranker weights
        # are never needed.  Skip loading them to avoid wasting 60-90 seconds
        # and ~2 GB of RAM at startup.
        if settings.use_modal_retrieval_models:
            logger.info(
                "USE_MODAL_RETRIEVAL_MODELS=true — skipping local BGE-M3/reranker warm-up. "
                "All embedding and reranking will go to Modal GPU."
            )
            return

        bge_ready, reason = bge_m3_cache_status()
        if not bge_ready:
            logger.warning("BGE-M3 cache not ready (%s) — skipping warm-up", reason)
            return
        try:
            from app.services.ingestion import _get_embedder, _get_reranker, _ML_EXECUTOR
            loop = _asyncio.get_event_loop()
            logger.info("Warming up BGE-M3 embedder in background…")
            await loop.run_in_executor(_ML_EXECUTOR, _get_embedder)
            logger.info("BGE-M3 embedder ready ✓")
            logger.info("Warming up cross-encoder reranker in background…")
            await loop.run_in_executor(_ML_EXECUTOR, _get_reranker)
            logger.info("Reranker ready ✓")
        except Exception as exc:
            logger.warning("Model warm-up failed (non-fatal, will load on first request): %s", exc)

    import asyncio as _asyncio
    _asyncio.create_task(_warmup_models())
    # ────────────────────────────────────────────────────────────────

    yield
    logger.info("Server stopped")


app = FastAPI(title="VoiceLearn AI — Phase 1+2", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open for local dev
    allow_methods=["*"],
    allow_headers=["*"],
    # Expose custom response headers so the browser fetch() API can read them.
    # X-Segments:            used by the temporary mixed TTS test route for segment debug info.
    # X-TTS-Engine:          Mode C — reports "IndicF5-MixedDirect" on the new test route.
    # X-TTS-Language-Mode:   Mode C — reports "mode-c-multilingual".
    # X-TTS-Latency-Ms:      Mode C — reports end-to-end inference latency in ms.
    # X-Normalized-Text-B64: Mode B — base64-encoded normalized Tamil text preview.
    expose_headers=["X-Segments", "X-TTS-Engine", "X-TTS-Language-Mode", "X-TTS-Latency-Ms", "X-Normalized-Text-B64"],
)

# ── TEMPORARY: Tamil TTS isolated test route ──────────────────────────────────
# Registers POST /api/v1/test/tamil-tts on this development server.
# Remove these two lines after TTS testing is complete.
from app.api.v1.routes import test_tamil_tts as _test_tamil_tts_module  # noqa: E402
app.include_router(_test_tamil_tts_module.router, prefix="/api/v1")
# ── END TEMPORARY ────────────────────────────────────────────────────────

# ── TEMPORARY: English TTS isolated test route ─────────────────────────────────
# Registers POST /api/v1/test/english-tts on this development server.
# Remove these two lines after English TTS testing is complete.
from app.api.v1.routes import test_english_tts as _test_english_tts_module  # noqa: E402
app.include_router(_test_english_tts_module.router, prefix="/api/v1")
# ── END TEMPORARY ─────────────────────────────────────────────────────────────

# ── TEMPORARY: Mixed TTS isolated test route ──────────────────────────────────
# Registers POST /api/v1/test/mixed-tts on this development server.
# Remove these two lines after mixed TTS testing is complete.
from app.api.v1.routes import test_mixed_tts as _test_mixed_tts_module  # noqa: E402
app.include_router(_test_mixed_tts_module.router, prefix="/api/v1")
# ── END TEMPORARY ─────────────────────────────────────────────────────────────────

# ── TEMPORARY: Mode C Multilingual TTS isolated test route ────────────────────
# Registers POST /api/v1/test/multilingual-tts on this development server.
# Mode C experiment: raw mixed Tamil+English text → ONE IndicF5 call → ONE WAV.
# Remove these two lines after Mode C evaluation is complete.
from app.api.v1.routes import test_multilingual_tts as _test_multilingual_tts_module  # noqa: E402
app.include_router(_test_multilingual_tts_module.router, prefix="/api/v1")
# ── END TEMPORARY ─────────────────────────────────────────────────────────────

# ── TEMPORARY: Mode D Indic Parler Mixed TTS isolated test route ───────────────
# Registers POST /api/v1/test/indic-parler-mixed-tts on this development server.
# Mode D experiment: raw mixed Tamil+English text → ONE ai4bharat/indic-parler-tts call → ONE WAV.
# Uses its own Modal app (voicelearn-indic-parler-mixed-tts) and URL (MODAL_INDIC_PARLER_MIXED_TTS_URL).
# Does NOT use IndicF5, Parler-TTS Mini v1, or any existing TTS service.
# Gated by USE_INDIC_PARLER_MIXED_TTS_TEST=true.
# Remove these two lines after Mode D evaluation is complete.
from app.api.v1.routes import test_indic_parler_mixed_tts as _test_indic_parler_mixed_tts_module  # noqa: E402
app.include_router(_test_indic_parler_mixed_tts_module.router, prefix="/api/v1")

# Registers POST /api/v1/test/sinhala-tts and its /romanize helper on the
# local app.main_stt server used by the /test page.
from app.api.v1.routes import test_sinhala_tts as _test_sinhala_tts_module  # noqa: E402
app.include_router(_test_sinhala_tts_module.router, prefix="/api/v1")
# ── END TEMPORARY ─────────────────────────────────────────────────────────────

# ── TEMPORARY: Sinhala ASR isolated test route ────────────────────────────────
# Registers POST /api/v1/test/sinhala-asr on this development server.
# Uses Lingalingeswaran/whisper-small-sinhala (voicelearn-sinhala-whisper-asr).
# Completely isolated from Tamil ASR, English ASR, RAG, TTS, and all other routes.
# Gated by USE_SINHALA_ASR_TEST=true.
# Remove these two lines after Sinhala ASR evaluation is complete.
from app.api.v1.routes import test_sinhala_asr as _test_sinhala_asr_module  # noqa: E402
app.include_router(_test_sinhala_asr_module.router, prefix="/api/v1")
# ── END TEMPORARY ─────────────────────────────────────────────────────────────

# ── In-memory document registry ───────────────────────────────────────────────
# { user_id: { doc_id: { filename, file_type, chunk_count, uploaded_at } } }
_local_docs: dict[str, dict[str, dict]] = {}

SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".xlsx", ".txt", ".md"}

LANG_MAP = {
    "english": "en",
    "tamil":   "ta",
    "sinhala": "si",
    "mixed":   None,
}

ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/wav", "audio/mpeg",
    "audio/ogg", "audio/mp4", "audio/x-m4a",
    "application/octet-stream",
}

# Languages that require native (non-Latin) Unicode script in their transcript
_NATIVE_SCRIPT_LANGS = {"tamil", "sinhala"}


def _is_romanized(text: str, threshold: float = 0.75) -> bool:
    """Return True if text is predominantly Latin/ASCII characters.

    Whisper sometimes outputs Tamil/Sinhala speech as romanized English
    (e.g. 'Naai' instead of 'நாய்'). We detect this by checking whether
    the vast majority of alphabetic characters fall in the ASCII range.
    If so, we trigger a Qwen-based script-correction step.
    """
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return False
    latin = sum(1 for c in alpha if ord(c) < 128)
    return (latin / len(alpha)) >= threshold


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "whisper_configured": bool(settings.modal_whisper_url),
    }


# ── Phase 1: Voice Transcribe ─────────────────────────────────────────────────

@app.post("/api/v1/voice/transcribe")
async def transcribe(
    audio_file: UploadFile = File(...),
    language: str = Form(default="english"),
):
    """STT — calls Whisper Large V3 on Modal, returns transcript."""
    lang = language.lower()
    if lang not in LANG_MAP:
        raise HTTPException(400, detail=f"Invalid language '{language}'. Use: english, tamil, sinhala, mixed")

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(400, detail="Audio file is empty")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(413, detail="Audio exceeds 25MB limit")

    try:
        result = await call_whisper(audio_bytes, audio_file.filename or "recording.webm", language)
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=f"Whisper error: {e}")

    transcript = result.get("transcript", "")

    # ── Script correction ────────────────────────────────────────────────────
    # STRICT MODE: script correction only runs for Tamil / Sinhala modes.
    # English mode is NEVER corrected — user selected English = English output only.
    # Only if user chose Tamil/Sinhala and Whisper romanized the output do we fix it.
    #
    # SKIP for Tamil when lemuralabs/tamil-asr-qwen3 handled it — the Qwen3 ASR
    # model always outputs correct Unicode Tamil, so script correction is unnecessary.
    from app.core.config import get_settings as _get_settings
    _using_indic = (
        lang == "tamil"
        and bool(_get_settings().modal_indic_stt_url.strip())
    )

    detected_iso = result.get("detected_language", "")
    selected_native_language = lang if lang in {"tamil", "sinhala"} else None

    if selected_native_language and transcript and _is_romanized(transcript) and not _using_indic:
        get_logger(__name__).info(
            "Romanized %s detected ('%s…') — running script correction",
            selected_native_language, transcript[:30]
        )
        try:
            correction = await call_script_corrector(transcript, selected_native_language)
            corrected = correction.get("corrected_text", "").strip()
            if corrected and corrected != transcript:
                transcript = corrected
                get_logger(__name__).info("Script corrected → '%s…'", transcript[:30])
        except Exception as e:
            get_logger(__name__).warning("Script correction failed: %s — keeping original", e)
    # ── End script correction ─────────────────────────────────────────────────

    return {
        "transcript":        transcript,
        "detected_language": (
            LANG_MAP[selected_native_language]
            if selected_native_language
            else detected_iso or lang[:2]
        ),
        "selected_language": lang,
        "duration_ms":       result.get("duration_ms", 0),
    }


# ── Phase 1.5: Text-to-Speech ────────────────────────────────────────────────

@app.post("/api/v1/voice/tts")
async def text_to_speech(body: dict):
    """
    Proxy the TTS request to the language-appropriate Modal endpoint.
    Returns raw WAV audio bytes (audio/wav).
    Supports: english, tamil, sinhala, mixed.
    """
    from fastapi.responses import Response

    text = (body.get("text") or "").strip()
    language = body.get("language", "english")

    if not text:
        raise HTTPException(400, detail="text cannot be empty")

    try:
        if language == "tamil":
            # Route Tamil answers through the appropriate TTS engine:
            #   - mixed script (Tamil + English) and USE_MIXED_TTS=true
            #       → mixed orchestrator (IndicF5 + Parler-TTS, segment-aware)
            #       → if orchestrator fails: fall back to whole-text Tamil TTS
            #   - pure Tamil (or USE_MIXED_TTS=false)
            #       → existing IndicF5 path (unchanged)
            from app.services.modal_client import call_tamil_tts
            from app.services.mixed_tts import detect_script, synthesize_mixed_tts

            _script = detect_script(text)
            _mixed_enabled = get_settings().use_mixed_tts

            if _mixed_enabled and _script == "mixed":
                get_logger(__name__).info(
                    "/api/v1/voice/tts: mixed script detected — routing to mixed orchestrator"
                )
                audio_bytes = await synthesize_mixed_tts(text)
                if audio_bytes is None:
                    # STRICT fallback: mixed synthesis aborted (a segment failed).
                    # Fall back to single-model Tamil TTS so the user still gets audio,
                    # even though English terms may be mispronounced.
                    get_logger(__name__).warning(
                        "/api/v1/voice/tts: mixed TTS failed for '%s…' — "
                        "falling back to whole-text Tamil TTS (English terms may sound off)",
                        text[:50],
                    )
                    audio_bytes = await call_tamil_tts(text)
                    if audio_bytes is None:
                        raise RuntimeError(
                            "Mixed TTS failed and Tamil TTS fallback also failed."
                        )
            else:
                # Pure Tamil, or mixed TTS disabled — existing path unchanged.
                audio_bytes = await call_tamil_tts(text)
                if audio_bytes is None:
                    raise RuntimeError("Tamil TTS is unavailable.")

        elif language == "english":
            # Parler-TTS Mini v1 produces higher-quality English than MMS-TTS.
            from app.services.modal_client import call_english_tts

            audio_bytes = await call_english_tts(text)
            if audio_bytes is None:
                # USE_ENGLISH_TTS=false or endpoint not configured — fall back to MMS-TTS
                from app.services.modal_client import call_tts
                audio_bytes = await call_tts(text, language)
        else:
            from app.services.modal_client import call_tts

            audio_bytes = await call_tts(text, language)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        get_logger(__name__).warning("TTS unavailable: %s", e)
        raise HTTPException(503, detail=f"TTS service unavailable: {e}")


# ── Tamil-only TTS (AI4Bharat Indic Parler-TTS) ─────────────────────────

@app.post("/api/v1/voice/tamil-tts")
async def tamil_text_to_speech(body: dict):
    """
    Tamil-only TTS proxy → Modal AI4Bharat Indic Parler-TTS endpoint.

    This is a SEPARATE endpoint from /api/v1/voice/tts (MMS-TTS).
    Only call this for Tamil text. Sinhala and English must NOT use this.

    Returns raw WAV audio bytes (audio/wav).
    Returns 503 if Tamil TTS is unavailable; the caller must show text-only.
    Returns 400 if the text is empty.
    """
    from fastapi.responses import Response
    from app.services.modal_client import call_tamil_tts

    text = (body.get("text") or "").strip()

    if not text:
        raise HTTPException(400, detail="text cannot be empty")

    logger = get_logger(__name__)
    audio_bytes = await call_tamil_tts(text)

    if audio_bytes is None:
        # TTS disabled or failed — return a clear 503 so the frontend shows text only.
        logger.info("/api/v1/voice/tamil-tts: TTS unavailable or disabled, returning 503")
        raise HTTPException(
            503,
            detail="Tamil TTS is currently unavailable. Text answer is still shown.",
        )

    return Response(content=audio_bytes, media_type="audio/wav")


# ── TEMPORARY: Tamil TTS inline route removed ────────────────────────────────
# The test route POST /api/v1/test/tamil-tts is now ONLY registered via
# app.include_router(_test_tamil_tts_module.router, prefix="/api/v1") above.
# The previous inline @app.post duplicate has been removed to avoid route
# conflicts and ensure the Pydantic 'engine' field is properly validated.
# ── END TEMPORARY ─────────────────────────────────────────────────────────────


# ── English-only TTS (Parler-TTS Mini v1) ──────────────────────────────

@app.post("/api/v1/voice/english-tts")
async def english_text_to_speech(body: dict):
    """
    English-only TTS proxy → Modal Parler-TTS Mini v1 endpoint.

    This is a SEPARATE endpoint from /api/v1/voice/tts (MMS-TTS).
    Only call this for English text. Tamil and Sinhala must NOT use this.

    Returns raw WAV audio bytes (audio/wav).
    Returns 503 if English TTS is unavailable; the caller must show text-only.
    Returns 400 if the text is empty.

    Optional: pass 'description' to control the speaking style.
    If omitted, the default educational voice description is used.
    """
    from fastapi.responses import Response
    from app.services.modal_client import call_english_tts

    text = (body.get("text") or "").strip()
    description = (body.get("description") or "").strip()

    if not text:
        raise HTTPException(400, detail="text cannot be empty")

    logger = get_logger(__name__)
    audio_bytes = await call_english_tts(text, description)

    if audio_bytes is None:
        # TTS disabled or failed — return a clear 503 so the frontend shows text only.
        logger.info("/api/v1/voice/english-tts: TTS unavailable or disabled, returning 503")
        raise HTTPException(
            503,
            detail="English TTS is currently unavailable. Text answer is still shown.",
        )

    return Response(content=audio_bytes, media_type="audio/wav")


# ── Mixed Tamil + English TTS (orchestrator) ─────────────────────────────

@app.post("/api/v1/voice/mixed-tts")
async def mixed_text_to_speech(body: dict):
    """
    Mixed Tamil + English TTS proxy → orchestrates IndicF5 + Parler-TTS Mini v1.

    Called by the frontend when it detects a Tamil-mode RAG answer that contains
    both Tamil Unicode and Latin (English) script.  The orchestrator segments the
    text, synthesizes each part with the appropriate model, normalises the audio,
    and returns one continuous WAV.

    Failure policy: if any segment fails, the entire call returns 503.  The
    frontend must then show text-only (the RAG answer is never affected).

    Returns raw WAV audio bytes (audio/wav).
    Returns 503 if USE_MIXED_TTS=false or synthesis fails.
    Returns 400 if text is empty.
    """
    from fastapi.responses import Response
    from app.services.mixed_tts import synthesize_mixed_tts

    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, detail="text cannot be empty")

    logger = get_logger(__name__)
    settings = get_settings()

    if not settings.use_mixed_tts:
        logger.info("/api/v1/voice/mixed-tts: USE_MIXED_TTS=false — returning 503")
        raise HTTPException(
            503,
            detail="Mixed TTS is disabled (USE_MIXED_TTS=false). Text answer is still shown.",
        )

    audio_bytes = await synthesize_mixed_tts(text)
    if audio_bytes is None:
        logger.warning(
            "/api/v1/voice/mixed-tts: synthesis failed for '%s…' — returning 503",
            text[:50],
        )
        raise HTTPException(
            503,
            detail=(
                "Mixed TTS synthesis failed — one or more segments returned no audio. "
                "Text answer is still shown."
            ),
        )

    return Response(content=audio_bytes, media_type="audio/wav")


# ── Phase 2: Document Upload ──────────────────────────────────────────────────

@app.post("/api/v1/documents/upload", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    """Use the canonical persistent upload flow in the local test server too."""
    from app.api.v1.routes.documents import upload_document_endpoint

    return await upload_document_endpoint(file=file, current_user=None)


# ── Phase 2: List Documents ───────────────────────────────────────────────────

@app.get("/api/v1/documents/")
async def list_documents():
    """Return the same persistent document list used by the production API."""
    from app.api.v1.routes.documents import list_documents as persistent_list_documents

    return await persistent_list_documents(current_user=None)


# ── Phase 2: Correct Transcript (Gemma 4 12B IT) ──────────────────────────────

@app.post("/api/v1/documents/correct-transcript")
async def correct_transcript(body: dict):
    """
    Correct a raw ASR transcript using Gemma 4 12B IT (Modal).

    This endpoint is called ONLY when the user explicitly clicks "Fix Transcript".
    It corrects obvious ASR errors (spelling, misrecognized words, punctuation)
    while preserving the speaker's original meaning exactly. It does NOT rewrite,
    enhance, or convert the transcript into a search query.

    Returns { corrected_transcript: str }.
    """
    transcript = (body.get("transcript") or "").strip()
    language = body.get("language", "english")
    detected_language = body.get("detected_language", language)
    effective_language = language if language in {"tamil", "sinhala"} else (detected_language or language)

    if not transcript:
        raise HTTPException(400, detail="transcript cannot be empty")

    try:
        from app.services.modal_client import call_transcript_corrector
        result = await call_transcript_corrector(transcript, effective_language)
        corrected_transcript = result.get("corrected_transcript", transcript)
    except Exception as e:
        get_logger(__name__).warning("Transcript corrector unavailable: %s", e)
        raise HTTPException(503, detail=f"Transcript corrector unavailable: {e}")

    return {"corrected_transcript": corrected_transcript}


# ── Phase 2: Delete Document ──────────────────────────────────────────────────

@app.delete("/api/v1/documents/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """Delete persistent metadata and its BGE-M3 chunks together."""
    from app.api.v1.routes.documents import delete_document as persistent_delete_document

    await persistent_delete_document(document_id=document_id, current_user=None)
    return


# ── Phase 2: Ask / RAG ────────────────────────────────────────────────────────


@app.post("/api/v1/documents/ask")
async def ask_question(body: dict):
    """
    Phase 2 RAG pipeline:
    1. Query selection — uses corrected_transcript if provided by the frontend
       (user chose 'Fix Transcript' path), otherwise uses the raw ASR transcript.
       Gemma is NEVER called automatically here; correction is always user-triggered.
    2. ChromaDB retrieval (Dense + BM25 + RRF + Reranker)
    3. RAG answer via Gemma 4 12B (Modal)
    4. Localization — ensures answer is in the user's selected language
    """
    import time as _time
    _request_start = _time.perf_counter()

    transcript = (body.get("transcript") or "").strip()
    language = body.get("language", "english")          # user's UI selection (response language)
    detected_language = body.get("detected_language", language)  # actual spoken language from Whisper
    # Frontend sends corrected_transcript only when user explicitly chose 'Fix Transcript'.
    # If absent, the raw transcript is used directly -- no automatic Gemma call.
    corrected_transcript = (body.get("corrected_transcript") or "").strip()

    # Tamil/Sinhala selected by the user must remain Tamil/Sinhala throughout
    # RAG, even if Whisper misclassifies a short recording.
    effective_language = language if language in {"tamil", "sinhala"} else (detected_language or language)

    if not transcript:
        raise HTTPException(400, detail="transcript cannot be empty")

    logger = get_logger(__name__)
    settings = get_settings()

    # Step 1 -- Query selection (no model call here)
    # If the user explicitly corrected the transcript, use that; otherwise use raw.
    if corrected_transcript:
        query = corrected_transcript
        logger.info("Using user-corrected transcript [%s]: %s", effective_language, query[:80])
    else:
        query = transcript
        logger.info("Using raw ASR transcript [%s]: %s", effective_language, query[:80])

    # Step 2 — Hybrid Retrieval (Dense + BM25 + RRF + Reranker)
    # When USE_MODAL_RETRIEVAL_MODELS=true: embedding + reranking go to Modal GPU.
    # When false:  existing local CPU path (BGE-M3 cache check enforced).
    if not settings.use_modal_retrieval_models:
        bge_ready, _ = bge_m3_cache_status()
        if not bge_ready:
            raise HTTPException(
                503,
                detail="BGE-M3 model unavailable: local cache is incomplete or corrupt.",
            )

    raw_chunks = []
    _retrieval_start = _time.perf_counter()
    try:
        from app.services.ingestion import hybrid_query_chunks
        raw_chunks = await hybrid_query_chunks(query, "guest", n_results=5)
    except Exception as e:
        logger.warning("Hybrid retrieval failed, falling back to dense: %s", e)
        try:
            from app.services.ingestion import query_chunks
            raw_chunks = await query_chunks(query, "guest", n_results=5)
        except Exception as e2:
            logger.warning("Dense fallback also failed: %s", e2)
    _retrieval_elapsed = _time.perf_counter() - _retrieval_start
    logger.info("[TIMING] retrieval_total: %.3fs (%d chunks)", _retrieval_elapsed, len(raw_chunks))


    if not raw_chunks:
        no_content_messages = {
            "tamil": "பதிவேற்றிய ஆவணங்களில் இந்தக் கேள்விக்கான தொடர்புடைய தகவல் கிடைக்கவில்லை. முதலில் வாசிக்கக்கூடிய lecture document ஒன்றைப் பதிவேற்றவும்.",
            "sinhala": "ඔබ උඩුගත කළ ලේඛනවල මෙම ප්‍රශ්නයට අදාළ තොරතුරු හමු නොවීය. කරුණාකර කියවිය හැකි lecture document එකක් උඩුගත කරන්න.",
            "mixed": "Ungal uploaded documents-la indha kelvikku relevant content kidaikkala. Mudhal-la readable lecture document upload pannunga.",
        }
        return {
            "answer": no_content_messages.get(
                language,
                "I couldn't find relevant content in your uploaded documents. Please upload lecture materials first.",
            ),
            "corrected_transcript": query,
            "references": [],
        }

    # Step 3 — RAG generation
    # Pass effective_language so Gemma knows what language to respond in
    context_texts = [c["text"] for c in raw_chunks]
    _rag_start = _time.perf_counter()
    try:
        rag_result = await call_rag_generator(query, context_texts, effective_language)
        raw_answer = rag_result.get("answer", "I couldn't generate an answer right now.")
    except Exception as e:
        logger.error("RAG generator unavailable: %s", e)
        raw_answer = "RAG generation is not available. Please deploy the Modal RAG endpoint."
    logger.info("[TIMING] gemma_rag: %.3fs", _time.perf_counter() - _rag_start)

    # Step 4 — Localization: ensure answer is in the user's SELECTED language
    # (which may differ from their spoken language for mixed-mode scenarios)
    _loc_start = _time.perf_counter()
    try:
        loc_result = await call_localizer(raw_answer, language)
        answer = loc_result.get("localized_text", raw_answer)
    except Exception as e:
        logger.warning("Localizer unavailable: %s", e)
        answer = raw_answer
    logger.info("[TIMING] localization: %.3fs", _time.perf_counter() - _loc_start)

    # Step 5 — References
    references = []
    for idx, chunk in enumerate(raw_chunks):
        meta = chunk.get("metadata", {})
        try:
            references.append({
                "document_id": meta.get("document_id", str(uuid.uuid4())),
                "filename":    meta.get("filename", "unknown"),
                "chunk_index": idx,
                "page":        meta.get("page"),
                "excerpt":     chunk["text"][:200] + ("..." if len(chunk["text"]) > 200 else ""),
                "score":       round(chunk.get("score", 0.0), 4),
            })
        except Exception:
            pass

    logger.info("[TIMING] total_request: %.3fs", _time.perf_counter() - _request_start)

    return {
        "answer":               answer,
        "corrected_transcript": query,
        "references":           references,
        "detected_language":    effective_language,
    }
