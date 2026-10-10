"""Conservative cleanup for Sinhala-only OCR output."""

import re
import unicodedata
from typing import Any


MIN_SINHALA_CHARS = 2


def _is_sinhala(char: str) -> bool:
    return "\u0d80" <= char <= "\u0dff"


def clean_sinhala_text(text: str) -> str:
    """Remove hallucinated Latin letters, digits, and symbols.

    The application recognises Sinhala handwriting only. Normal punctuation is
    retained, while a result must contain at least two Sinhala code points to
    be treated as meaningful text.
    """
    normalized = unicodedata.normalize("NFC", str(text or ""))
    cleaned = "".join(
        char
        for char in normalized
        if _is_sinhala(char)
        or char in {"\u200c", "\u200d"}
        or char.isspace()
        or unicodedata.category(char).startswith("P")
    )
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned).strip()
    # Removing a page number such as ``3)`` must not leave a leading ``)``.
    cleaned = re.sub(r"^[^\u0d80-\u0dff]+", "", cleaned)

    if sum(_is_sinhala(char) for char in cleaned) < MIN_SINHALA_CHARS:
        return ""
    return cleaned


def clean_ocr_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return OCR lines containing useful Sinhala text, preserving metadata."""
    cleaned_lines = []
    previous_text = None
    for line in lines:
        text = clean_sinhala_text(line.get("text", ""))
        if not text or text == previous_text:
            continue
        cleaned_line = dict(line)
        cleaned_line["text"] = text
        cleaned_lines.append(cleaned_line)
        previous_text = text
    return cleaned_lines
