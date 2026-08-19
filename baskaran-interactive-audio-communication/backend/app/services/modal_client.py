"""
Modal endpoint HTTP client.

Each Modal endpoint is a plain HTTPS URL that accepts JSON POST requests.
This module provides typed async callers for each endpoint.
No modal SDK dependency in the application layer — just httpx.
"""

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Shared async client with a generous timeout for cold-start
_http = httpx.AsyncClient(timeout=120.0)


def _auth_headers() -> dict[str, str]:
    """Modal token authentication headers."""
    s = get_settings()
    if s.modal_token_id and s.modal_token_secret:
        return {
            "Modal-Token-Id": s.modal_token_id,
            "Modal-Token-Secret": s.modal_token_secret,
        }
    return {}


# ── BGE-M3 Embedding (Modal GPU) ─────────────────────────────────────────────────

async def call_bge_embed(texts: list[str]) -> list[list[float]]:
    """
    Embed texts using the Modal BGE-M3 GPU endpoint (BGEEmbedder /embed).

    Uses normalize_embeddings=True to match the existing Chroma collection,
    which was built with the same normalization.  The returned vectors are
    always 1024-D; a dimension mismatch causes an immediate RuntimeError so
    the caller never silently uses a wrong embedding model.

    Raises RuntimeError on ANY failure — embedding failure must not fall back
    to a different model (requirement 8).
    """
    url = get_settings().modal_bge_embed_url.strip()
    if not url:
        raise RuntimeError(
            "MODAL_BGE_EMBED_URL is not configured. "
            "Deploy backend/modal_endpoints/bge_retrieval.py first."
        )

    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"texts": texts, "normalize": True},
            timeout=120.0,   # 30-60 s cold-start on T4; 0.2-0.5 s warm
        )
        response.raise_for_status()
    except Exception as exc:
        # Never silently swallow the error — surface it immediately.
        logger.error(
            "call_bge_embed failed (%s: %s)",
            type(exc).__name__, exc,
        )
        raise RuntimeError(
            f"Modal BGE-M3 embedding failed ({type(exc).__name__}): {exc}. "
            "Do not fall back to a different embedding model — vectors would "
            "be incompatible with the existing Chroma collection."
        ) from exc

    data = response.json()
    embeddings: list[list[float]] = data["embeddings"]
    dim: int = data.get("dimension", len(embeddings[0]) if embeddings else 0)

    # Hard guard: reject wrong-dimension vectors before they corrupt Chroma.
    for vec in embeddings:
        if len(vec) != 1024:
            raise RuntimeError(
                f"Modal BGE-M3 returned {len(vec)}-D vectors; expected 1024. "
                "Check that the deployed endpoint uses BAAI/bge-m3 unchanged."
            )

    logger.debug("call_bge_embed: %d texts → %d-D vectors", len(texts), dim)
    return embeddings


# ── BGE Reranker (Modal GPU) ────────────────────────────────────────────────────

async def call_bge_rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank candidates using the Modal BGE-reranker-v2-m3 GPU endpoint.

    On failure: logs a warning and returns the original candidate list unchanged
    (graceful fallback to RRF order — requirement 8).
    """
    if not candidates or len(candidates) < 2:
        return candidates   # nothing to rerank

    url = get_settings().modal_bge_rerank_url.strip()
    if not url:
        logger.warning(
            "MODAL_BGE_RERANK_URL not configured — skipping reranking, using RRF order"
        )
        return candidates

    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={
                "query": query,
                "candidates": candidates,
                "top_k": top_k,
            },
            timeout=60.0,   # reranker is fast on GPU; 45 s covers cold-start
        )
        response.raise_for_status()
        data = response.json()
        ranked: list[dict] = data["ranked"]
        logger.debug(
            "call_bge_rerank: %d candidates → top-%d returned",
            len(candidates), len(ranked),
        )
        return ranked
    except Exception as exc:
        logger.warning(
            "call_bge_rerank failed (%s: %s) — falling back to RRF order",
            type(exc).__name__, exc,
        )
        # Graceful fallback: return original candidates in RRF order (unranked)
        return candidates[:top_k]


async def call_whisper(audio_bytes: bytes, filename: str, language_hint: str) -> dict:
    """
    Call the appropriate STT endpoint based on language.

    Routing:
      - Tamil  + MODAL_INDIC_STT_URL configured → lemuralabs/tamil-asr-qwen3 (Tamil-native Qwen3 ASR)
      - Tamil  + MODAL_INDIC_STT_URL NOT set     → Whisper (fallback)
      - All other languages                       → Whisper Large V3

    Args:
        audio_bytes: Raw audio file bytes (webm/wav/mp3/ogg).
        filename:    Original filename (used as a hint for format detection).
        language_hint: User-selected language code ("english", "tamil", "sinhala", "mixed").

    Returns:
        dict with keys: transcript, detected_language, duration_ms
    """
    settings = get_settings()

    # Route Tamil to lemuralabs/tamil-asr-qwen3 if the endpoint is configured.
    # If the Qwen3-ASR model fails (crash-loop / cold-start timeout / any error),
    # automatically fall back to Whisper Large V3 with language_hint="tamil"
    # so Tamil transcription always works.
    indic_url = settings.modal_indic_stt_url.strip()
    if language_hint.lower() == "tamil" and indic_url:
        logger.info("Routing Tamil audio to IndicConformer STT (%s bytes)", len(audio_bytes))
        try:
            return await call_indic_stt(audio_bytes, filename)
        except Exception as indic_exc:
            logger.warning(
                "IndicConformer STT failed (%s: %s) — falling back to Whisper for Tamil",
                type(indic_exc).__name__,
                indic_exc,
            )
            # Fall through to Whisper below with Tamil forced

    # All other languages (or Tamil fallback) → Whisper Large V3
    url = settings.modal_whisper_url.strip()

    if not url:
        raise RuntimeError("MODAL_WHISPER_URL is not configured. Deploy the Whisper endpoint first.")

    # For Tamil fallback, keep language_hint as "tamil" so Whisper forces Tamil
    effective_hint = language_hint
    logger.info("Calling Whisper endpoint: %s bytes, hint=%s", len(audio_bytes), effective_hint)

    response = await _http.post(
        url,
        headers=_auth_headers(),
        files={"audio_file": (filename, audio_bytes, "application/octet-stream")},
        data={"language_hint": effective_hint},
        # Backwards-compatible with the currently deployed endpoint, where
        # language_hint was accidentally defined as a query parameter rather
        # than a multipart Form field.  New deployments read the form field;
        # old deployments read this query parameter.
        params={"language_hint": effective_hint},
    )
    response.raise_for_status()
    return response.json()


async def call_indic_stt(audio_bytes: bytes, filename: str) -> dict:
    """
    Call the lemuralabs/tamil-asr-qwen3 endpoint for Tamil speech-to-text.

    This endpoint always returns clean Tamil Unicode text (no romanization).
    Called automatically by call_whisper() when language_hint == "tamil".

    Args:
        audio_bytes: Raw audio bytes (webm/wav/mp3).
        filename:    Original filename for format detection.

    Returns:
        dict with keys: transcript, detected_language, duration_ms
    """
    url = get_settings().modal_indic_stt_url.strip()
    if not url:
        raise RuntimeError("MODAL_INDIC_STT_URL is not configured. Deploy tamil_asr_qwen3.py first.")

    logger.info("Calling lemuralabs/tamil-asr-qwen3 STT endpoint: %s bytes", len(audio_bytes))

    response = await _http.post(
        url,
        headers=_auth_headers(),
        files={"audio_file": (filename, audio_bytes, "application/octet-stream")},
        data={"language_hint": "tamil"},
        timeout=180.0,   # IndicConformer cold-start on T4 can take ~90-120s
    )
    response.raise_for_status()
    return response.json()


async def call_transcript_corrector(transcript: str, language: str) -> dict:
    """Call the Gemma 4 12B transcript correction endpoint (mode=correct).

    Used when the user explicitly clicks 'Fix Transcript'. Corrects obvious ASR
    errors while preserving the speaker's original meaning exactly. Does NOT
    rewrite, enhance, or convert the transcript into a search query.

    Args:
        transcript: Raw ASR transcript from Whisper / IndicConformer.
        language:   Spoken language ("english", "tamil", "sinhala", "mixed").

    Returns:
        dict with key 'corrected_transcript' containing the corrected text.
    """
    url = get_settings().modal_transcript_corrector_url
    if not url:
        logger.warning("MODAL_TRANSCRIPT_CORRECTOR_URL not set -- returning original transcript")
        return {"corrected_transcript": transcript}

    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"transcript": transcript, "language": language, "mode": "correct"},
            timeout=120.0,  # Gemma 4 12B cold-start on A100 can take 60-120s
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning(
            "call_transcript_corrector failed (%s): %s -- returning raw transcript",
            type(exc).__name__,
            exc,
        )
        return {"corrected_transcript": transcript}


async def call_script_corrector(text: str, language: str) -> dict:
    """Convert romanized Tamil/Sinhala back to native Unicode script.

    Called automatically inside /api/v1/voice/transcribe when Whisper outputs
    phonetically transcribed Latin text instead of Tamil/Sinhala Unicode.
    Reuses the Gemma 4 12B correct_transcript endpoint with mode='script_correct',
    which applies a separate strict script-restoration prompt -- not the
    user-visible transcript-correction prompt.

    Args:
        text:     Romanized text from Whisper (e.g. "Naai, Naai, Naai").
        language: "tamil" or "sinhala".

    Returns:
        dict with key 'corrected_text' containing the native-script version.
    """
    url = get_settings().modal_transcript_corrector_url
    if not url:
        logger.warning("MODAL_TRANSCRIPT_CORRECTOR_URL not set -- cannot correct script")
        return {"corrected_text": text}

    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"transcript": text, "language": language, "mode": "script_correct"},
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        corrected = data.get("corrected_transcript", text).strip()
        # Safety: if model returned empty or same text, keep original
        return {"corrected_text": corrected if corrected else text}
    except Exception as exc:
        logger.warning(
            "call_script_corrector failed (%s): %s -- keeping original text",
            type(exc).__name__,
            exc,
        )
        return {"corrected_text": text}


async def call_rag_generator(query: str, context_chunks: list[str], language: str) -> dict:
    """Call the Gemma 4 RAG generation endpoint.

    Wraps the request in a try/except so a cold-start timeout, network error,
    or non-200 response never leaves the frontend stuck in "Searching…" forever.
    Raises RuntimeError on failure so the caller can surface a clean error message.
    """
    url = get_settings().modal_rag_generator_url
    if not url:
        raise RuntimeError("MODAL_RAG_GENERATOR_URL is not configured.")

    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"query": query, "context": context_chunks, "language": language},
            timeout=120.0,  # Gemma 4 12B cold-start on A100 can take ~60-120s
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.error(
            "call_rag_generator failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        raise RuntimeError(
            f"RAG generation failed ({type(exc).__name__}): {exc}. "
            "The Modal endpoint may be cold-starting — please retry in a moment."
        ) from exc


async def call_localizer(text: str, language: str) -> dict:
    """Call the Qwen2.5-7B localization endpoint.

    Falls back to the original English text on any failure so the pipeline
    never breaks even when the Modal endpoint is not yet deployed.
    """
    url = get_settings().modal_localizer_url
    if not url:
        logger.warning("MODAL_LOCALIZER_URL not set — returning original text")
        return {"localized_text": text}

    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"text": text, "language": language},
            timeout=120.0,  # Qwen2.5-7B cold-start on T4 can take ~60-90s
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning(
            "call_localizer failed (%s): %s — returning original text",
            type(exc).__name__,
            exc,
        )
        return {"localized_text": text}


async def call_tts(text: str, language: str) -> bytes:
    """Call the MMS-TTS endpoint. Returns raw audio bytes (wav)."""
    url = get_settings().modal_tts_url
    if not url:
        raise RuntimeError("MODAL_TTS_URL is not configured.")

    response = await _http.post(
        url,
        headers=_auth_headers(),
        json={"text": text, "language": language},
    )
    response.raise_for_status()
    return response.content


# ── Tamil-only TTS (AI4Bharat Indic Parler-TTS) ────────────────────────────

async def call_tamil_tts_direct(text: str) -> bytes | None:
    """Call the AI4Bharat Indic Parler-TTS endpoint unconditionally.

    TEMPORARY — used ONLY by the isolated TTS test route
    (POST /api/v1/test/tamil-tts).  Unlike call_tamil_tts(), this function
    does NOT check the use_tamil_tts feature flag, so it works even when
    USE_TAMIL_TTS=false (which keeps the production RAG→TTS disabled during
    the test period).

    Returns raw WAV bytes on success, or None on any failure.
    REMOVE this function after TTS testing is complete.
    """
    import time as _time

    settings = get_settings()

    url = settings.modal_tamil_tts_url.strip()
    if not url:
        logger.warning(
            "call_tamil_tts_direct: MODAL_TAMIL_TTS_URL is not configured — "
            "Tamil TTS test will be skipped. Deploy tamil_parler_tts.py first."
        )
        return None

    _t0 = _time.perf_counter()
    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"text": text, "language": "tamil"},
            timeout=180.0,   # A10G cold-start for Parler-TTS can take ~90-120s
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        warmth = "cold-start" if elapsed > 15.0 else "warm"
        logger.info(
            "[TIMING] tamil_tts_direct_generation: %.3fs (container=%s, %d chars)",
            elapsed, warmth, len(text),
        )
        return response.content

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_tamil_tts_direct failed after %.2fs (%s: %s)",
            elapsed, type(exc).__name__, exc,
        )
        return None


# ── Mode C — Multilingual TTS (IndicF5 direct, raw mixed text, DEV ONLY) ──────

async def call_multilingual_tts_direct(text: str) -> bytes | None:
    """Mode C experiment: send RAW Tamil+English mixed text directly to IndicF5.

    DEVELOPMENT / TEST ONLY — used exclusively by
    POST /api/v1/test/multilingual-tts.

    Unlike call_tamil_tts_direct(), this function:
    - Does NOT pre-process the text in any way
    - Does NOT transliterate English words to Tamil phonetics
    - Does NOT segment by script
    - Does NOT split Tamil and English calls

    The original mixed text is sent to the IndicF5 endpoint as-is.
    IndicF5 is built on the F5-TTS flow-matching architecture and was trained
    on 1,417 hours of multilingual Indic data — it has polyglot zero-shot
    capabilities that may handle Tamil+English code-switching in a single pass.

    The endpoint still receives language="tamil" because that is what the
    deployed IndicF5 Modal endpoint validates (it only checks that the
    request is not requesting an entirely different language service).

    Returns raw WAV bytes on success, or None on any failure.
    REMOVE this function after Mode C evaluation is complete.
    """
    import time as _time

    settings = get_settings()

    url = settings.modal_tamil_tts_url.strip()
    if not url:
        logger.warning(
            "call_multilingual_tts_direct: MODAL_TAMIL_TTS_URL is not configured — "
            "Mode C TTS test will be skipped. Deploy tamil_parler_tts.py first."
        )
        return None

    _t0 = _time.perf_counter()
    try:
        logger.info(
            "[MODE-C] Sending raw mixed text (%d chars) directly to IndicF5 — "
            "NO transliteration, NO segmentation, NO split.",
            len(text),
        )
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"text": text, "language": "tamil"},
            timeout=240.0,  # A10G cold-start ~90-120 s; longer text needs extra margin
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        warmth = "cold-start" if elapsed > 15.0 else "warm"
        logger.info(
            "[TIMING][MODE-C] multilingual_tts_direct: %.3fs (container=%s, %d chars)",
            elapsed, warmth, len(text),
        )
        return response.content

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_multilingual_tts_direct failed after %.2fs (%s: %s) — "
            "Mode C only; Tamil/English/ModeA/ModeB are unaffected.",
            elapsed, type(exc).__name__, exc,
        )
        return None

# ── END Mode C ─────────────────────────────────────────────────────────────────


# ── Mode D — Indic Parler Mixed TTS (ai4bharat/indic-parler-tts, DEV ONLY) ────

async def call_indic_parler_mixed_tts_direct(text: str, description: str = "") -> bytes | None:
    """Mode D experiment: send RAW Tamil+English mixed text to ai4bharat/indic-parler-tts.

    DEVELOPMENT / TEST ONLY — used exclusively by
    POST /api/v1/test/indic-parler-mixed-tts.

    Mode D rules (strictly enforced — no exceptions):
      - Does NOT pre-process the text in any way
      - Does NOT transliterate English words to Tamil phonetics
      - Does NOT use eSpeak
      - Does NOT use IndicXlit
      - Does NOT segment by script (Tamil vs English)
      - Does NOT split into two separate TTS calls and join
      - Does NOT use IndicF5 (different from Mode A, B, C)
      - Does NOT use Parler-TTS Mini v1 (different from English TTS)

    The original mixed Tamil+English text is sent in ONE call to the
    ai4bharat/indic-parler-tts model — a unified multilingual model trained
    on 1,806 hours of Indic+English data, capable of code-switched synthesis.

    URL used: MODAL_INDIC_PARLER_MIXED_TTS_URL
    This URL is SEPARATE from MODAL_TAMIL_TTS_URL and MODAL_ENGLISH_TTS_URL.
    Failure here ONLY affects Mode D — no other TTS path is touched.

    Returns raw WAV bytes (44,100 Hz) on success, or None on any failure.
    REMOVE this function after Mode D evaluation is complete.
    """
    import time as _time

    settings = get_settings()

    url = settings.modal_indic_parler_mixed_tts_url.strip()
    if not url:
        logger.warning(
            "call_indic_parler_mixed_tts_direct: MODAL_INDIC_PARLER_MIXED_TTS_URL is not configured — "
            "Mode D TTS test will be skipped. Deploy indic_parler_mixed_tts.py first."
        )
        return None

    payload: dict = {"text": text}
    if description.strip():
        payload["description"] = description.strip()

    _t0 = _time.perf_counter()
    try:
        logger.info(
            "[MODE-D] Sending raw mixed text (%d chars) to ai4bharat/indic-parler-tts — "
            "NO transliteration, NO segmentation, NO split, NOT IndicF5, NOT Parler Mini v1.",
            len(text),
        )
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json=payload,
            timeout=300.0,  # A10G cold-start for indic-parler-tts ~90-120s; ~938M params
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        # Validate we actually got audio
        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type and "octet-stream" not in content_type:
            logger.warning(
                "[MODE-D] Unexpected content-type '%s' after %.2fs — Mode D only affected.",
                content_type, elapsed,
            )
            return None

        content = response.content
        if not content:
            logger.warning("[MODE-D] Empty audio bytes after %.2fs — Mode D only affected.", elapsed)
            return None

        warmth = "cold-start" if elapsed > 15.0 else "warm"
        logger.info(
            "[TIMING][MODE-D] indic_parler_mixed_tts_direct: %.3fs (container=%s, %d chars)",
            elapsed, warmth, len(text),
        )
        return content

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_indic_parler_mixed_tts_direct failed after %.2fs (%s: %s) — "
            "Mode D only; Tamil/English/ModeA/ModeB/ModeC and RAG are unaffected.",
            elapsed, type(exc).__name__, exc,
        )
        return None

# ── END Mode D ─────────────────────────────────────────────────────────────────


async def call_tamil_tts(text: str) -> bytes | None:
    """Call the AI4Bharat Indic Parler-TTS endpoint for Tamil synthesis.

    Returns raw WAV bytes on success, or None on any failure.
    This function is intentionally non-raising so that TTS failure never
    breaks the RAG text response shown to the user.

    Args:
        text: Tamil text to synthesize.

    Returns:
        bytes (audio/wav) on success, None if TTS is disabled or fails.
    """
    import time as _time

    settings = get_settings()

    if not settings.use_tamil_tts:
        logger.debug("call_tamil_tts: USE_TAMIL_TTS=false — skipping Tamil TTS")
        return None

    url = settings.modal_tamil_tts_url.strip()
    if not url:
        logger.warning(
            "call_tamil_tts: MODAL_TAMIL_TTS_URL is not configured — "
            "Tamil TTS will be skipped. Deploy tamil_parler_tts.py first."
        )
        return None

    _t0 = _time.perf_counter()
    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"text": text, "language": "tamil"},
            timeout=180.0,   # A10G cold-start for Parler-TTS can take ~90-120s
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        # Heuristic: if the round-trip was very long, the container was cold.
        warmth = "cold-start" if elapsed > 15.0 else "warm"
        logger.info(
            "[TIMING] tamil_tts_generation: %.3fs (container=%s, %d chars)",
            elapsed, warmth, len(text),
        )
        return response.content

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_tamil_tts failed after %.2fs (%s: %s) — "
            "Tamil text answer is unaffected; audio will not be available.",
            elapsed, type(exc).__name__, exc,
        )
        return None


# ── English TTS (Parler-TTS Mini v1 on Modal T4) ───────────────────────

async def call_english_tts_direct(text: str, description: str = "") -> bytes | None:
    """Call the Parler-TTS Mini v1 endpoint unconditionally.

    TEMPORARY — used ONLY by the isolated TTS test route
    (POST /api/v1/test/english-tts).  Unlike call_english_tts(), this function
    does NOT check the use_english_tts feature flag, so it works even when
    USE_ENGLISH_TTS=false (which keeps the production RAG→TTS disabled during
    the test period).

    Returns raw WAV bytes on success, or None on any failure.
    REMOVE this function after English TTS testing is complete.
    """
    import time as _time

    settings = get_settings()

    url = settings.modal_english_tts_url.strip()
    if not url:
        logger.warning(
            "call_english_tts_direct: MODAL_ENGLISH_TTS_URL is not configured — "
            "English TTS test will be skipped. Deploy english_parler_tts.py first."
        )
        return None

    # Use the caller's description or the centrally configured default.
    effective_description = description.strip() or settings.english_tts_default_description

    _t0 = _time.perf_counter()
    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"text": text, "description": effective_description},
            timeout=180.0,  # T4 cold-start for Parler-TTS can take ~60-90s
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        # Validate we got audio content, not an error JSON
        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type and "octet-stream" not in content_type:
            logger.warning(
                "call_english_tts_direct: unexpected content-type '%s' after %.2fs",
                content_type, elapsed,
            )
            return None

        content = response.content
        if not content:
            logger.warning("call_english_tts_direct: empty audio bytes after %.2fs", elapsed)
            return None

        warmth = "cold-start" if elapsed > 15.0 else "warm"
        logger.info(
            "[TIMING] english_tts_direct_generation: %.3fs (container=%s, %d chars)",
            elapsed, warmth, len(text),
        )
        return content

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_english_tts_direct failed after %.2fs (%s: %s)",
            elapsed, type(exc).__name__, exc,
        )
        return None


async def call_english_tts(text: str, description: str = "") -> bytes | None:
    """Call the Parler-TTS Mini v1 endpoint for English synthesis.

    Returns raw WAV bytes on success, or None on any failure.
    This function is intentionally non-raising so that TTS failure never
    breaks the RAG text response shown to the user.

    Args:
        text:        English text to synthesize.
        description: Optional Parler-TTS style description.  If empty,
                     the centrally configured default educational voice
                     description is used.

    Returns:
        bytes (audio/wav) on success, None if TTS is disabled or fails.
    """
    import time as _time

    settings = get_settings()

    if not settings.use_english_tts:
        logger.debug("call_english_tts: USE_ENGLISH_TTS=false — skipping English TTS")
        return None

    url = settings.modal_english_tts_url.strip()
    if not url:
        logger.warning(
            "call_english_tts: MODAL_ENGLISH_TTS_URL is not configured — "
            "English TTS will be skipped. Deploy english_parler_tts.py first."
        )
        return None

    # Use the caller's description or the centrally configured default.
    effective_description = description.strip() or settings.english_tts_default_description

    _t0 = _time.perf_counter()
    try:
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"text": text, "description": effective_description},
            timeout=180.0,  # T4 cold-start for Parler-TTS can take ~60-90s
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        # Validate content type
        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type and "octet-stream" not in content_type:
            logger.warning(
                "call_english_tts: unexpected content-type '%s' after %.2fs",
                content_type, elapsed,
            )
            return None

        content = response.content
        if not content:
            logger.warning("call_english_tts: empty audio bytes after %.2fs", elapsed)
            return None

        warmth = "cold-start" if elapsed > 15.0 else "warm"
        logger.info(
            "[TIMING] english_tts_generation: %.3fs (container=%s, %d chars)",
            elapsed, warmth, len(text),
        )
        return content

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_english_tts failed after %.2fs (%s: %s) — "
            "English text answer is unaffected; audio will not be available.",
            elapsed, type(exc).__name__, exc,
        )
        return None


# ── Sinhala VITS TTS (dialoglk/SinhalaVITS-TTS-F1, DEV ONLY) ─────────────────

async def call_sinhala_vits_tts_direct(text: str) -> bytes | None:
    """Call the SinhalaVITS-TTS-F1 endpoint unconditionally.

    TEMPORARY — used ONLY by the isolated Sinhala TTS test route
    (POST /api/v1/test/sinhala-tts).

    Architecture (completely isolated from all other TTS):
      - Uses MODAL_SINHALA_VITS_TTS_URL — separate from MODAL_TAMIL_TTS_URL
        and MODAL_ENGLISH_TTS_URL and MODAL_INDIC_PARLER_MIXED_TTS_URL.
      - Calls the voicelearn-sinhala-vits-tts Modal app.
      - The Modal container applies romanizer.py (Sinhala → romanized Sinhala)
        then runs Coqui VITS inference at 22,050 Hz.
      - Failure here ONLY affects the Sinhala test route. Tamil TTS, English TTS,
        Mixed TTS (all modes), ASR, RAG, and production routing are untouched.

    Returns raw WAV bytes (22,050 Hz, PCM 16-bit) on success, None on any failure.
    REMOVE this function after Sinhala TTS evaluation is complete.
    """
    import time as _time

    settings = get_settings()

    url = settings.modal_sinhala_vits_tts_url.strip()
    if not url:
        logger.warning(
            "call_sinhala_vits_tts_direct: MODAL_SINHALA_VITS_TTS_URL is not configured — "
            "Sinhala TTS test will be skipped. "
            "Deploy backend/modal_endpoints/sinhala_vits_tts.py first."
        )
        return None

    _t0 = _time.perf_counter()
    try:
        logger.info(
            "[SINHALA-VITS] Synthesizing %d chars via SinhalaVITS-TTS-F1 "
            "(dialoglk/SinhalaVITS-TTS-F1, T4 GPU, 22050 Hz)",
            len(text),
        )
        response = await _http.post(
            url,
            headers=_auth_headers(),
            json={"text": text},
            timeout=180.0,   # T4 cold-start ~60-90s; VITS synthesis is fast once warm
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        # Validate we actually got audio
        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type and "octet-stream" not in content_type:
            logger.warning(
                "[SINHALA-VITS] Unexpected content-type '%s' after %.2fs — "
                "Sinhala test only; no other TTS affected.",
                content_type, elapsed,
            )
            return None

        content = response.content
        if not content:
            logger.warning(
                "[SINHALA-VITS] Empty audio bytes after %.2fs — Sinhala test only.",
                elapsed,
            )
            return None

        warmth = "cold-start" if elapsed > 15.0 else "warm"
        logger.info(
            "[TIMING][SINHALA-VITS] synthesis: %.3fs (container=%s, %d chars, %d bytes)",
            elapsed, warmth, len(text), len(content),
        )
        return content

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_sinhala_vits_tts_direct failed after %.2fs (%s: %s) — "
            "Sinhala test only; Tamil/English/Mixed TTS and RAG are unaffected.",
            elapsed, type(exc).__name__, exc,
        )
        return None


async def call_sinhala_vits_romanize(text: str) -> dict | None:
    """Call the /romanize debug endpoint on the SinhalaVITS Modal container.

    TEMPORARY — used ONLY by POST /api/v1/test/sinhala-tts/romanize.
    Returns {"original": "...", "romanized": "..."} or None on failure.

    This is purely for debugging the romanizer behavior on Sinhala text,
    English words, and mixed input during the evaluation period.
    REMOVE this function after Sinhala TTS evaluation is complete.
    """
    import time as _time

    settings = get_settings()

    romanize_url = settings.modal_sinhala_vits_tts_romanize_url.strip()
    if not romanize_url:
        logger.warning(
            "call_sinhala_vits_romanize: MODAL_SINHALA_VITS_TTS_ROMANIZE_URL is not configured."
        )
        return None

    _t0 = _time.perf_counter()
    try:
        response = await _http.post(
            romanize_url,
            headers=_auth_headers(),
            json={"text": text},
            timeout=120.0,
        )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0
        logger.debug(
            "[SINHALA-VITS] romanize call: %.3fs | %d chars",
            elapsed, len(text),
        )
        return response.json()
    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_sinhala_vits_romanize failed after %.2fs (%s: %s)",
            elapsed, type(exc).__name__, exc,
        )
        return None

# ── END TEMPORARY SINHALA VITS TTS ────────────────────────────────────────────


async def call_sinhala_phonetic_gemma(english_span: str) -> str | None:
    """Call only the dedicated phonetic method on the already-deployed Gemma app.

    This has a separate URL and cannot affect RAG generation or transcript
    correction.  The request contains one English span only.
    """
    url = get_settings().modal_sinhala_phonetics_url.strip()
    if not url:
        return None
    try:
        response = await _http.post(url, headers=_auth_headers(), json={"english": english_span}, timeout=45.0)
        response.raise_for_status()
        return str(response.json().get("phonetic", "")).strip() or None
    except Exception as exc:
        logger.warning("Sinhala phonetic Gemma call failed (%s: %s)", type(exc).__name__, exc)
        return None


# ── TEMPORARY Sinhala ASR (Lingalingeswaran/whisper-small-sinhala, DEV ONLY) ──

async def call_sinhala_asr_direct(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
) -> dict | None:
    """Send audio to the isolated Sinhala Whisper ASR Modal endpoint.

    TEMPORARY — used ONLY by POST /api/v1/test/sinhala-asr.

    Architecture (completely isolated from all other ASR):
      - Uses MODAL_SINHALA_ASR_URL — separate from MODAL_WHISPER_URL and
        MODAL_INDIC_STT_URL.
      - Calls the voicelearn-sinhala-whisper-asr Modal app.
      - The Modal container runs Lingalingeswaran/whisper-small-sinhala
        with forced Sinhala transcription mode (language="si", task="transcribe").
      - Failure here ONLY affects the Sinhala ASR test route.
        Tamil ASR, English ASR, RAG, TTS, and all other routes are untouched.

    Returns dict with {"text", "latency_ms", "duration_seconds", "engine"}
    on success, or None on any failure.
    REMOVE this function after Sinhala ASR evaluation is complete.
    """
    import time as _time

    settings = get_settings()
    url = settings.modal_sinhala_asr_url.strip()
    if not url:
        logger.warning(
            "call_sinhala_asr_direct: MODAL_SINHALA_ASR_URL is not configured — "
            "Sinhala ASR test will be skipped. "
            "Deploy backend/modal_endpoints/sinhala_whisper_asr.py first."
        )
        return None

    _t0 = _time.perf_counter()
    try:
        import httpx as _httpx

        logger.info(
            "[SINHALA-ASR] Transcribing %d bytes via whisper-small-sinhala (T4 GPU)",
            len(audio_bytes),
        )

        # Send multipart/form-data — matches the Modal endpoint's UploadFile expectation
        async with _httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                url,
                headers=_auth_headers(),
                files={"audio_file": (filename, audio_bytes, content_type)},
            )
        response.raise_for_status()
        elapsed = _time.perf_counter() - _t0

        result = response.json()
        warmth = "cold-start" if elapsed > 15.0 else "warm"
        transcript_preview = str(result.get("text", ""))[:80]

        logger.info(
            "[TIMING][SINHALA-ASR] %.3fs (%s) | transcript='%s…'",
            elapsed, warmth, transcript_preview,
        )
        return result

    except Exception as exc:
        elapsed = _time.perf_counter() - _t0
        logger.warning(
            "call_sinhala_asr_direct failed after %.2fs (%s: %s) — "
            "Sinhala ASR test only; Tamil/English ASR and all other routes are unaffected.",
            elapsed, type(exc).__name__, exc,
        )
        return None

# ── END TEMPORARY SINHALA ASR ──────────────────────────────────────────────────
