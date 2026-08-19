"""Tamil-script normalisation for the experimental single-voice mixed TTS path.

Conversion pipeline for each Latin/English token
-------------------------------------------------
Priority  Layer                    Source
--------  -----------------------  -----------------------------------
  1       Pronunciation dictionary  mixed_tts_pronunciation.py
  2       Acronym / abbrev. rules   _acronym_pronunciation() below
  3       eSpeak NG G2P             mixed_tts_g2p.espeak_to_tamil()
  4       IndicXlit transliteration _indic_xlit_tamil() below
  5       Original token            pass-through (last resort)

All layer calls are wrapped so that any failure is silent and the next layer
is tried automatically.  The whole pipeline never raises.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.core.logging import get_logger
from app.services.mixed_tts_pronunciation import PRONUNCIATION_DICTIONARY

logger = get_logger(__name__)

# A Latin token can retain internal hyphens (``cloud-based`` / ``GPT-4``), but
# a trailing hyphen before Tamil is deliberately left outside the token.
_LATIN_TOKEN = re.compile(r"[A-Za-z]+(?:-[A-Za-z0-9]+)*|[A-Za-z]+(?=\d)")


@lru_cache(maxsize=1)
def _indic_xlit_engine() -> Any | None:
    """Load IndicXlit lazily so an unavailable optional model never breaks TTS."""
    try:
        from ai4bharat.transliteration import XlitEngine  # type: ignore[import-not-found]

        return XlitEngine(src_script_type="roman")
    except Exception as exc:
        logger.info("IndicXlit unavailable; using curated pronunciations/eSpeak/original fallback (%s)", exc)
        return None


def _indic_xlit_tamil(word: str) -> str | None:
    engine = _indic_xlit_engine()
    if engine is None:
        return None
    try:
        # IndicXlit's public Python API returns candidates for a word.  Accept
        # either the documented mapping form or a direct candidate sequence to
        # remain compatible with package releases used by Modal deployments.
        result = engine.translit_word(word, lang_code="ta")
        if isinstance(result, dict):
            candidates = result.get("ta") or result.get("tam") or []
        else:
            candidates = result
        if isinstance(candidates, str):
            return candidates.strip() or None
        if candidates:
            candidate = candidates[0]
            return str(candidate).strip() or None
    except Exception as exc:
        logger.warning("IndicXlit failed for %r: %s", word, exc)
    return None


def _acronym_pronunciation(word: str) -> str | None:
    """Speak unlisted all-caps abbreviations as Tamil letter names."""
    if not (word.isupper() and word.isalpha() and 2 <= len(word) <= 8):
        return None
    letters = {
        "A": "ஏ", "B": "பி", "C": "சி", "D": "டி", "E": "ஈ", "F": "எஃப்",
        "G": "ஜி", "H": "எச்", "I": "ஐ", "J": "ஜே", "K": "கே", "L": "எல்",
        "M": "எம்", "N": "என்", "O": "ஓ", "P": "பி", "Q": "க்யூ", "R": "ஆர்",
        "S": "எஸ்", "T": "டி", "U": "யூ", "V": "வி", "W": "டபிள்யூ", "X": "எக்ஸ்",
        "Y": "வை", "Z": "ஸெட்",
    }
    return " ".join(letters[letter] for letter in word)


@lru_cache(maxsize=512)
def _normalize_latin_token(token: str) -> str:
    """Convert one Latin/English token to Tamil script using the 5-layer pipeline.

    Results are LRU-cached (maxsize=512) so repeated tokens within the same
    response skip eSpeak and IndicXlit entirely.

    Hyphenated tokens (e.g. ``cloud-based``, ``GPT-4``) are split at ``-``
    and each part is normalised independently before rejoining with ``-``.
    """
    key = token.casefold()

    # ── Layer 1: Pronunciation dictionary ────────────────────────────────────
    if key in PRONUNCIATION_DICTIONARY:
        result = PRONUNCIATION_DICTIONARY[key]
        logger.debug("Mode B token %r → [dict] %r", token, result)
        return result

    # ── Layer 2: Acronym / abbreviation rule ─────────────────────────────────
    acronym = _acronym_pronunciation(token)
    if acronym:
        logger.debug("Mode B token %r → [acronym] %r", token, acronym)
        return acronym

    # ── Hyphen split: normalise each sub-part independently ──────────────────
    # This also avoids passing ``cloud-based`` as a single opaque token to
    # eSpeak or IndicXlit, which neither handles well.
    if "-" in token:
        return "-".join(_normalize_latin_token(part) for part in token.split("-"))

    # ── Layer 3: eSpeak NG G2P → Tamil phoneme mapper ───────────────────────
    try:
        from app.services.mixed_tts_g2p import espeak_to_tamil
        g2p_result = espeak_to_tamil(token)
        if g2p_result:
            logger.debug("Mode B token %r → [g2p] %r", token, g2p_result)
            return g2p_result
    except Exception as g2p_exc:
        logger.warning("G2P layer error for %r: %s", token, g2p_exc)

    # ── Layer 4: IndicXlit transliteration fallback ───────────────────────────
    xlit = _indic_xlit_tamil(token)
    if xlit:
        logger.debug("Mode B token %r → [indicxlit] %r", token, xlit)
        return xlit

    # ── Layer 5: Original token (last resort) ────────────────────────────────
    logger.debug("Mode B token %r → [original]", token)
    return token


def normalize_mixed_text_for_indicf5(text: str) -> str:
    """Return a TTS-only Tamil-oriented copy; never mutate the displayed text.

    Tamil Unicode, whitespace, punctuation, digits, markdown markers, and
    Tamil suffixes adjacent to a Latin word are retained exactly.  Only Latin
    alphabetic spans are replaced using the 5-layer pronunciation pipeline:

        1. pronunciation dictionary
        2. acronym rule
        3. eSpeak NG G2P → Tamil mapper
        4. IndicXlit transliteration
        5. original token

    Parameters
    ----------
    text : str
        The original mixed Tamil + English text (e.g. a RAG answer).

    Returns
    -------
    str
        Tamil-script-oriented text ready to send to IndicF5.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _LATIN_TOKEN.sub(lambda match: _normalize_latin_token(match.group(0)), text)

