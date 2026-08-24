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


def prepare_mixed_tts_text(text: str) -> str:
    """Return speech-friendly Tamil/English text without changing either script.

    The Indic Parler prompt tokenizer supports both Tamil and Latin characters,
    so English terms are intentionally preserved.  Only visual markup and
    characters that produce unnatural speech are removed.
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

    # Keep language-bearing Tamil and English text untouched.  Normalize only
    # punctuation that otherwise tends to be verbalized or causes abrupt audio.
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
