"""
Mixed Tamil + English TTS orchestration service.

Public API
----------
detect_script(text)        → "tamil" | "english" | "mixed"
segment_mixed_text(text)   → list[{"language": "ta"|"en", "text": str}]
synthesize_mixed_tts(text) → bytes (WAV) | None

Audio normalization
-------------------
Uses Python stdlib `wave` for WAV I/O and `numpy` (already a transitive dep
via sentence-transformers) for PCM arithmetic and resampling.
NO new pip packages are required.

Failure policy (STRICT — by design)
------------------------------------
If ANY segment TTS call fails, the ENTIRE mixed synthesis returns None.
The caller must fall back to a single-model path or surface a 503.
We NEVER silently drop words, because a response missing a key English
term (e.g., a drug name or technical concept) could be meaningfully misleading.
"""

from __future__ import annotations

import asyncio
import io
import re
import time
import wave
from typing import Literal

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Tamil Unicode block: U+0B80 – U+0BFF ────────────────────────────────────
_TAMIL_LO = 0x0B80
_TAMIL_HI = 0x0BFF

# ── Audio output constants ────────────────────────────────────────────────────
# The deployed Tamil endpoint writes IndicF5 audio at 24 kHz; Parler-TTS Mini
# typically writes 44.1 kHz.  Keep the existing mixed-output rate at 22.05 kHz
# for compatibility, and normalize every segment to it before joining.
_TARGET_RATE      = 22_050   # Hz — existing mixed-output sample rate
_TARGET_CHANNELS  = 1        # mono
_TARGET_SAMPWIDTH = 2        # 16-bit PCM

# ── Silence durations (milliseconds) ─────────────────────────────────────────
_SILENCE_SENTENCE_MS   = 120  # after  . ? ! । (sentence end)
_SILENCE_CLAUSE_MS     = 40   # after  , ; :
_SILENCE_TRANSITION_MS = 60   # language boundary (ta↔en) with no punctuation
_BOUNDARY_FADE_MS      = 8    # suppress clicks without an audible gap
_TARGET_SPEECH_RMS     = 0.10 # approx. -20 dBFS, active speech only
_MAX_PEAK              = 0.92 # preserve headroom for the final PCM WAV

# Modal can briefly return no audio while a container is becoming ready.  A
# mixed request has many independent calls, so retrying an individual segment
# is far more reliable than failing the complete passage on that first blip.
_SEGMENT_TTS_ATTEMPTS = 3
_SEGMENT_RETRY_DELAY_SECONDS = 2.0

_SENTENCE_END_CHARS = frozenset(".?!।")
_CLAUSE_END_CHARS   = frozenset(",;:")
_MODE_B_MAX_CHARS = 700


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  Script detection
# ═══════════════════════════════════════════════════════════════════════════════

def _is_tamil_char(c: str) -> bool:
    return _TAMIL_LO <= ord(c) <= _TAMIL_HI


def _is_latin_alpha(c: str) -> bool:
    return c.isalpha() and ord(c) < 128


def detect_script(text: str) -> Literal["tamil", "english", "mixed"]:
    """
    Classify text as pure Tamil, pure English, or mixed.

    Only alphabetic characters count for classification; spaces, digits,
    punctuation, markdown markers, and parentheses are ignored.

    Returns
    -------
    "tamil"   ≥ 90% of meaningful chars are Tamil Unicode (U+0B80–0BFF)
    "english" ≥ 90% of meaningful chars are Latin alphabetic (ASCII)
    "mixed"   anything in between

    Examples
    --------
    >>> detect_script("நாய்கள் மிகவும் விசுவாசமானவை.")
    'tamil'
    >>> detect_script("Artificial intelligence helps students.")
    'english'
    >>> detect_script("Chocolate-ல் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்.")
    'mixed'
    """
    tamil_count = 0
    latin_count = 0

    for ch in text:
        if _is_tamil_char(ch):
            tamil_count += 1
        elif _is_latin_alpha(ch):
            latin_count += 1
        # digits / punctuation / spaces / markdown — ignored

    total = tamil_count + latin_count
    if total == 0:
        # No alphabetic content at all (numbers, punctuation only)
        return "english"

    if tamil_count / total >= 0.90:
        return "tamil"
    if latin_count / total >= 0.90:
        return "english"
    return "mixed"


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  Mixed-text segmenter
# ═══════════════════════════════════════════════════════════════════════════════

def segment_mixed_text(text: str) -> list[dict]:
    """
    Split code-switched text into an ordered list of language-labelled segments.

    Each segment: ``{"language": "ta" | "en", "text": str}``

    Rules
    -----
    * Iterate character-by-character using script type.
    * Tamil Unicode chars → "ta";  Latin alpha → "en".
    * Neutral characters (digits, punctuation, spaces, hyphens) accumulate
      inside the current segment until the next script boundary.
    * Adjacent same-language segments are merged automatically (no tiny calls).
    * Tamil grammatical suffixes on Latin tokens (e.g. "Chocolate-ல்") are
      correctly split: "Chocolate-" → en, "ல்…" → ta.
    * Returns ``[]`` for empty / whitespace-only input.

    Examples
    --------
    "Chocolate-ல் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்."
    →
    [{"language": "en", "text": "Chocolate-"},
     {"language": "ta", "text": "ல் உள்ள"},
     {"language": "en", "text": "theobromine"},
     {"language": "ta", "text": "நாய்களுக்கு நஞ்சாகும்."}]
    """
    if not text or not text.strip():
        return []

    segments: list[dict] = []
    current_lang: str | None = None
    buf: list[str] = []

    def _flush() -> None:
        nonlocal current_lang, buf
        if buf and current_lang:
            raw = "".join(buf)
            if raw.strip():
                if segments and segments[-1]["language"] == current_lang:
                    # Merge with the previous segment of the same language
                    segments[-1]["text"] += raw
                else:
                    segments.append({"language": current_lang, "text": raw})
        buf = []

    for ch in text:
        if _is_tamil_char(ch):
            new_lang = "ta"
        elif _is_latin_alpha(ch):
            new_lang = "en"
        else:
            # Neutral: attach to the current buffer regardless of language
            buf.append(ch)
            continue

        if new_lang != current_lang:
            _flush()
            current_lang = new_lang

        buf.append(ch)

    _flush()  # flush any remaining chars

    # Strip leading/trailing whitespace inside each segment text
    result: list[dict] = []
    for seg in segments:
        t = seg["text"].strip()
        if t:
            result.append({"language": seg["language"], "text": t})

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  Audio utilities (numpy + wave stdlib — no new deps)
# ═══════════════════════════════════════════════════════════════════════════════

def _wav_bytes_to_pcm(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """
    Decode WAV bytes → (float32 PCM array normalised to [-1.0, 1.0], sample_rate).

    Multi-channel audio is collapsed to mono by averaging channels.

    Raises
    ------
    ValueError  if the sample width is not 1, 2, or 4 bytes.
    wave.Error  if the bytes are not a valid WAV file.
    """
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        nchannels  = wf.getnchannels()
        sampwidth  = wf.getsampwidth()
        framerate  = wf.getframerate()
        raw        = wf.readframes(wf.getnframes())

    if sampwidth == 1:
        # uint8 — centre is 128
        arr = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        arr = (arr - 128.0) / 128.0
    elif sampwidth == 2:
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        arr /= 32768.0
    elif sampwidth == 4:
        arr = np.frombuffer(raw, dtype=np.int32).astype(np.float32)
        arr /= 2_147_483_648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sampwidth} bytes")

    if nchannels > 1:
        arr = arr.reshape(-1, nchannels).mean(axis=1)

    return arr, framerate


def _resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """
    Resample float32 PCM from src_rate → dst_rate using linear interpolation.

    This is sufficient for speech intelligibility. A polyphase FIR filter would
    be marginally better but requires scipy, which is not a listed dependency.
    """
    if src_rate == dst_rate or len(samples) == 0:
        return samples

    new_length = max(1, int(len(samples) * dst_rate / src_rate))
    old_idx    = np.arange(len(samples), dtype=np.float64)
    new_idx    = np.linspace(0.0, len(samples) - 1, new_length, dtype=np.float64)
    return np.interp(new_idx, old_idx, samples).astype(np.float32)


def _make_silence_samples(ms: int) -> np.ndarray:
    """Return a float32 zero array for `ms` milliseconds at _TARGET_RATE."""
    n = int(_TARGET_RATE * ms / 1000)
    return np.zeros(n, dtype=np.float32)


def _match_loudness(pcm: np.ndarray) -> np.ndarray:
    """Match active speech to a conservative RMS level without clipping."""
    if pcm.size == 0:
        return pcm

    peak = float(np.max(np.abs(pcm)))
    if peak <= 1e-6:
        return pcm

    active = np.abs(pcm) >= max(0.01, peak * 0.02)
    speech = pcm[active]
    if speech.size:
        rms = float(np.sqrt(np.mean(np.square(speech, dtype=np.float64))))
        if rms > 1e-6:
            gain = float(np.clip(_TARGET_SPEECH_RMS / rms, 0.5, 2.0))
            pcm = pcm * gain

    peak = float(np.max(np.abs(pcm)))
    if peak > _MAX_PEAK:
        pcm = pcm * (_MAX_PEAK / peak)
    return pcm.astype(np.float32, copy=False)


def _fade_segment_edges(pcm: np.ndarray) -> np.ndarray:
    """Apply tiny linear fades at segment edges to avoid clicks."""
    if pcm.size == 0:
        return pcm

    fade_samples = min(int(_TARGET_RATE * _BOUNDARY_FADE_MS / 1000), pcm.size // 2)
    if fade_samples <= 1:
        return pcm

    faded = pcm.copy()
    ramp = np.linspace(0.0, 1.0, fade_samples, endpoint=True, dtype=np.float32)
    faded[:fade_samples] *= ramp
    faded[-fade_samples:] *= ramp[::-1]
    return faded


def _silence_between(prev_text: str, is_lang_transition: bool) -> np.ndarray:
    """
    Choose an appropriate silence gap based on the last character of the
    previous segment and whether the language is changing.
    """
    stripped   = prev_text.rstrip()
    last_char  = stripped[-1] if stripped else ""

    if last_char in _SENTENCE_END_CHARS:
        return _make_silence_samples(_SILENCE_SENTENCE_MS)
    if last_char in _CLAUSE_END_CHARS:
        return _make_silence_samples(_SILENCE_CLAUSE_MS)
    if is_lang_transition:
        return _make_silence_samples(_SILENCE_TRANSITION_MS)
    return np.empty(0, dtype=np.float32)


def _pcm_to_wav_bytes(pcm: np.ndarray) -> bytes:
    """Encode a float32 PCM array → 16-bit mono WAV bytes."""
    clipped = np.clip(pcm, -1.0, 1.0)
    int16   = (clipped * 32767.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(_TARGET_CHANNELS)
        wf.setsampwidth(_TARGET_SAMPWIDTH)
        wf.setframerate(_TARGET_RATE)
        wf.writeframes(int16.tobytes())

    return buf.getvalue()


async def _synthesize_segment_with_retry(
    language: str,
    text: str,
    *,
    english_description: str,
) -> bytes | None:
    """Generate one segment, retrying temporary Modal startup failures."""
    from app.services.modal_client import call_english_tts_direct, call_tamil_tts_direct

    for attempt in range(1, _SEGMENT_TTS_ATTEMPTS + 1):
        if language == "ta":
            wav_bytes = await call_tamil_tts_direct(text)
        else:
            wav_bytes = await call_english_tts_direct(text, english_description)

        if wav_bytes:
            return wav_bytes

        if attempt < _SEGMENT_TTS_ATTEMPTS:
            delay = _SEGMENT_RETRY_DELAY_SECONDS * attempt
            logger.warning(
                "Mixed TTS segment (%s, %d chars) returned no audio; retrying "
                "in %.1fs (%d/%d)",
                language.upper(), len(text), delay, attempt + 1, _SEGMENT_TTS_ATTEMPTS,
            )
            await asyncio.sleep(delay)

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  Mixed TTS orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

async def synthesize_mixed_tts(text: str, *, voice_matching: bool = True) -> bytes | None:
    """
    Orchestrate mixed Tamil + English TTS synthesis.

    Steps
    -----
    1. Segment ``text`` into language-labelled chunks.
    2. For each Tamil chunk → call the existing IndicF5 endpoint.
       For each English chunk → call the existing Parler-TTS Mini v1 endpoint.
    3. Decode each WAV segment → float32 PCM, resample to 22 050 Hz mono.
    4. For matched output, align active-speech loudness and fade segment edges.
    5. Insert punctuation-aware silence, concatenate, and encode one final WAV.

    Failure policy (STRICT)
    -----------------------
    If ANY segment TTS call returns None or a WAV decode error occurs, the
    ENTIRE orchestrator returns None immediately.  The caller is responsible for
    falling back (e.g. single-model Tamil TTS or a 503 response).

    We never silently skip words — a missing medical term or concept name in
    the synthesised audio could be genuinely misleading.

    Returns
    -------
    bytes   — one valid audio/wav on complete success
    None    — on any failure (the caller must handle this)
    """
    t_total = time.perf_counter()
    postprocess_elapsed = 0.0
    mixed_english_description = get_settings().mixed_english_tts_description

    # ── 1. Segment ────────────────────────────────────────────────────────────
    segments = segment_mixed_text(text)

    if not segments:
        logger.warning(
            "synthesize_mixed_tts: empty segment list for '%s…' — nothing to synthesize",
            text[:50],
        )
        return None

    logger.info(
        "synthesize_mixed_tts START | %d chars → %d segments",
        len(text), len(segments),
    )
    for i, seg in enumerate(segments):
        logger.info(
            "  [%d] %-2s  '%s%s'",
            i,
            seg["language"].upper(),
            seg["text"][:50],
            "…" if len(seg["text"]) > 50 else "",
        )

    # ── 2 & 3. Synthesize and decode each segment ─────────────────────────────
    pcm_parts: list[np.ndarray] = []
    prev_lang: str | None = None

    for i, seg in enumerate(segments):
        lang     = seg["language"]
        seg_text = seg["text"]

        t_seg = time.perf_counter()

        # Only mixed English receives the Jaya-aligned description. Pure
        # English still uses its existing central default unchanged.
        wav_bytes = await _synthesize_segment_with_retry(
            lang,
            seg_text,
            english_description=mixed_english_description if voice_matching else "",
        )

        elapsed_seg = time.perf_counter() - t_seg

        # ── STRICT FAILURE: abort entire synthesis if any segment fails ───────
        if not wav_bytes:
            logger.error(
                "synthesize_mixed_tts ABORTED | segment[%d] (%s) returned no audio "
                "after %.2fs — refusing to produce audio with missing words. "
                "Text: '%s…'",
                i, lang.upper(), elapsed_seg, seg_text[:50],
            )
            return None

        logger.info(
            "  [%d] ✓ %.3fs | %d WAV bytes",
            i, elapsed_seg, len(wav_bytes),
        )

        # Decode WAV → float32 PCM
        try:
            pcm, src_rate = _wav_bytes_to_pcm(wav_bytes)
        except Exception as decode_err:
            logger.error(
                "synthesize_mixed_tts ABORTED | segment[%d] WAV decode failed (%s)",
                i, decode_err,
            )
            return None

        # Resample and (for mixed voice matching) align levels / boundaries.
        t_postprocess = time.perf_counter()
        pcm = _resample(pcm, src_rate, _TARGET_RATE)
        if voice_matching:
            pcm = _fade_segment_edges(_match_loudness(pcm))
        postprocess_elapsed += time.perf_counter() - t_postprocess

        # ── 4. Insert silence before this segment ─────────────────────────────
        if prev_lang is not None:
            is_transition = (prev_lang != lang)
            silence = _silence_between(segments[i - 1]["text"], is_transition)
            if silence.size > 0:
                pcm_parts.append(silence)

        pcm_parts.append(pcm)
        prev_lang = lang

    # ── 5. Concatenate and encode ─────────────────────────────────────────────
    if not pcm_parts:
        logger.error("synthesize_mixed_tts: no PCM parts collected — aborting")
        return None

    try:
        t_join = time.perf_counter()
        final_pcm  = np.concatenate(pcm_parts)
        wav_output = _pcm_to_wav_bytes(final_pcm)
        join_elapsed = time.perf_counter() - t_join
    except Exception as enc_err:
        logger.error("synthesize_mixed_tts: WAV encoding failed (%s)", enc_err)
        return None

    total_elapsed = time.perf_counter() - t_total
    logger.info(
        "synthesize_mixed_tts DONE | %.3fs total | %.3fs normalize | %.3fs join | "
        "%d segments | %d output bytes",
        total_elapsed, postprocess_elapsed, join_elapsed, len(segments), len(wav_output),
    )
    return wav_output


def _split_at_sentence_boundaries(text: str, max_chars: int = _MODE_B_MAX_CHARS) -> list[str]:
    """Split only oversized text and only at natural sentence boundaries."""
    if len(text) <= max_chars:
        return [text]
    sentences = [piece.strip() for piece in re.split(r"(?<=[.?!।])\s+", text) if piece.strip()]
    if not sentences or any(len(sentence) > max_chars for sentence in sentences):
        # Do not degrade to phrase/word splitting: let IndicF5 reject this and
        # let the caller use Mode A, preserving the experimental safety policy.
        return []
    return sentences


async def synthesize_mixed_phonetic_tts(text: str, *, voice_matching: bool = True) -> tuple[bytes | None, str, bool]:
    """Experimental Mode B: normalise once, call IndicF5 once per sentence.

    Returns ``(wav, normalized_text, used_mode_a_fallback)``.  Any normalizer,
    endpoint, or WAV-validation failure falls back to the retained Mode A path.
    """
    from app.services.mixed_tts_phonetics import normalize_mixed_text_for_indicf5
    from app.services.modal_client import call_tamil_tts_direct

    try:
        normalized = normalize_mixed_text_for_indicf5(text)
        sentences = _split_at_sentence_boundaries(normalized)
        if not normalized.strip() or not sentences:
            raise ValueError("empty or unsafely long normalized text")

        wav_parts: list[bytes] = []
        for sentence in sentences:
            wav = await call_tamil_tts_direct(sentence)
            if not wav:
                raise RuntimeError("IndicF5 returned no audio")
            # Validate the response before returning it to the browser.
            _wav_bytes_to_pcm(wav)
            wav_parts.append(wav)

        if len(wav_parts) == 1:
            logger.info("Mode B mixed TTS succeeded in one IndicF5 call (%d chars)", len(normalized))
            return wav_parts[0], normalized, False

        # Long text is sentence-only split; reuse the existing WAV joiner.
        pcm_parts = [
            _resample(pcm, source_rate, _TARGET_RATE)
            for pcm, source_rate in (_wav_bytes_to_pcm(wav) for wav in wav_parts)
        ]
        return _pcm_to_wav_bytes(np.concatenate(pcm_parts)), normalized, False
    except Exception as exc:
        logger.warning("Mode B mixed TTS failed (%s); falling back to Mode A", exc)
        fallback_audio = await synthesize_mixed_tts(text, voice_matching=voice_matching)
        return fallback_audio, text, True
