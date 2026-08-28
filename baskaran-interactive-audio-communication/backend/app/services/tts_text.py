"""Text preparation helpers for speech synthesis."""

from __future__ import annotations

import html
import re
import unicodedata


_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_LIST_MARKER_RE = re.compile(r"(?m)^\s*(?:[-+*•●▪◦]\s+|\d+[.)]\s+)")
_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s*")
_QUOTE_RE = re.compile(r"(?m)^\s*>\s?")
_REFERENCE_RE = re.compile(r"\s*\[(?:\d+|source[^\]]*)\]", re.IGNORECASE)
_MARKDOWN_MARK_RE = re.compile(r"[*_~`]+")
_SPACE_RE = re.compile(r"[ \t\u00a0]+")

# Matches parenthesised content that is entirely Latin-script (English) —
# e.g. "(Chocolate)", "(Grapes and Raisins)", "(kidney failure)".
_PAREN_ENGLISH_RE = re.compile(r"\(\s*[A-Za-z][A-Za-z0-9 ,'\-]*\s*\)")

# Matches one or more consecutive Latin-script tokens (words / hyphenated
# words).  We strip them as whole "English runs" so no stray spaces remain.
_ENGLISH_RUN_RE = re.compile(r"[A-Za-z][A-Za-z0-9''\-]*(?:\s+[A-Za-z][A-Za-z0-9''\-]*)*")


def _strip_english_tokens(text: str) -> str:
    """Remove all Latin-script (English) words from text.

    Tamil characters, digits, Tamil punctuation, and sentence-level
    punctuation (.,!?) are preserved so the TTS model receives clean,
    uninterrupted Tamil text.

    Strategy
    --------
    1. Remove parenthesised English phrases first — e.g. "(Chocolate)".
    2. Remove any remaining bare Latin-script runs (words / phrases).
    3. Collapse whitespace / orphaned punctuation left behind.
    """
    # Step 1 — drop parenthesised English phrases whole
    value = _PAREN_ENGLISH_RE.sub(" ", text)

    # Step 2 — drop bare English word runs
    value = _ENGLISH_RUN_RE.sub(" ", value)

    # Step 3 — remove orphaned empty parentheses left behind
    value = re.sub(r"\(\s*\)", " ", value)

    # Step 4 — clean up stray punctuation clusters after English removal
    value = re.sub(r"[,;:]\s*\.", ".", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)

    return value


def prepare_mixed_tts_text(text: str) -> str:
    """Return speech-friendly Tamil-only text, stripping all English words.

    English terms that appear in the answer (scientific names, brand names,
    parenthesised translations, etc.) are removed so the Tamil TTS model is
    not asked to pronounce Latin-script text it cannot render reliably.
    Only Tamil characters, digits, and sentence punctuation are kept.
    """
    value = unicodedata.normalize("NFC", html.unescape(text or ""))
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = _HTML_TAG_RE.sub(" ", value)
    value = re.sub(r"```(?:\w+)?\s*", "", value)
    value = _MARKDOWN_LINK_RE.sub(r"\1", value)
    value = _URL_RE.sub(" ", value)
    value = _REFERENCE_RE.sub("", value)
    value = _HEADING_RE.sub("", value)
    value = _QUOTE_RE.sub("", value)
    value = _LIST_MARKER_RE.sub(". ", value)
    value = _MARKDOWN_MARK_RE.sub("", value)

    # Strip all English / Latin-script words and English-in-parentheses so
    # that only Tamil script reaches the TTS model.
    value = _strip_english_tokens(value)

    # Normalize punctuation that tends to be verbalized or causes abrupt audio.
    value = value.translate(
        str.maketrans(
            {
                "–": ", ",
                "—": ", ",
                "…": ". ",
                "•": ". ",
                "●": ". ",
                "▪": ". ",
                "◦": ". ",
                "|": ", ",
            }
        )
    )
    value = _SPACE_RE.sub(" ", value)
    value = re.sub(r"\s*\n\s*", ". ", value)
    value = re.sub(r"(?:\.\s*){2,}", ". ", value)
    value = re.sub(r"[:;]\s*\.\s*", ". ", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"([,.;:!?])(?!\s|$)", r"\1 ", value)
    value = _SPACE_RE.sub(" ", value).strip()
    return re.sub(r"^\.\s*", "", value)
