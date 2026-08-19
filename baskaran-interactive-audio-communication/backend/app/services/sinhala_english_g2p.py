"""CPU-only English pronunciation to Sinhala-script approximation.

This module is deliberately isolated from synthesis, RAG, and Gemma.  It uses
CMUdict when available, then the optional ``espeak-ng`` binary, and returns
``None`` rather than emitting an unsafe partial result.
"""
from __future__ import annotations

import re
import subprocess
from functools import lru_cache

from app.core.logging import get_logger

logger = get_logger(__name__)

_ARPABET = {
    "AA": "ආ", "AE": "ඇ", "AH": "අ", "AO": "ඔ", "AW": "අවු", "AY": "අයි",
    "EH": "එ", "ER": "අර්", "EY": "ඒ", "IH": "ඉ", "IY": "ඊ", "OW": "ඕ",
    "OY": "ඔයි", "UH": "උ", "UW": "ඌ",
    "B": "බ්", "CH": "ච්", "D": "ඩ්", "DH": "ද්", "F": "ෆ්", "G": "ග්",
    "HH": "හ්", "JH": "ජ්", "K": "ක්", "L": "ල්", "M": "ම්", "N": "න්",
    "NG": "ං", "P": "ප්", "R": "ර්", "S": "ස්", "SH": "ශ්", "T": "ට්",
    "TH": "ත්", "V": "ව්", "W": "ව්", "Y": "ය්", "Z": "ස්", "ZH": "ෂ්",
}
_IPA = [
    ("tʃ", "ච්"), ("dʒ", "ජ්"), ("eɪ", "ඒ"), ("aɪ", "අයි"), ("oʊ", "ඕ"),
    ("aʊ", "අවු"), ("ɔɪ", "ඔයි"), ("iː", "ඊ"), ("uː", "ඌ"), ("ɜː", "අර්"),
    ("ɚ", "අර්"), ("ə", "අ"), ("ɪ", "ඉ"), ("ɛ", "එ"), ("æ", "ඇ"), ("ʌ", "අ"),
    ("ɑ", "ආ"), ("ɔ", "ඔ"), ("ʊ", "උ"), ("i", "ඉ"), ("u", "උ"), ("b", "බ්"),
    ("d", "ඩ්"), ("f", "ෆ්"), ("g", "ග්"), ("h", "හ්"), ("k", "ක්"), ("l", "ල්"),
    ("m", "ම්"), ("n", "න්"), ("ŋ", "ං"), ("p", "ප්"), ("r", "ර්"), ("ɹ", "ර්"),
    ("s", "ස්"), ("ʃ", "ශ්"), ("t", "ට්"), ("θ", "ත්"), ("ð", "ද්"), ("v", "ව්"),
    ("w", "ව්"), ("j", "ය්"), ("z", "ස්"), ("ʒ", "ෂ්"),
]
_VOWEL_MATRAS = {"අ": "", "ආ": "ා", "ඇ": "ැ", "ඉ": "ි", "ඊ": "ී", "උ": "ු", "ඌ": "ූ", "එ": "ෙ", "ඒ": "ේ", "ඔ": "ො", "ඕ": "ෝ"}


def _compose(parts: list[str]) -> str | None:
    raw = "".join(parts)
    # Bind a following Sinhala vowel to the preceding closed consonant.
    for vowel, matra in _VOWEL_MATRAS.items():
        raw = raw.replace("්" + vowel, matra)
    raw = raw.replace("්අයි", "යි").replace("්අවු", "වු").replace("්ඔයි", "ොයි")
    return raw.strip() or None


@lru_cache(maxsize=1024)
def _cmudict_word(word: str) -> str | None:
    try:
        import cmudict  # lightweight optional package
        pronunciations = cmudict.dict().get(word.casefold())
    except Exception:
        return None
    if not pronunciations:
        return None
    parts = [_ARPABET.get(re.sub(r"\d", "", phoneme), "") for phoneme in pronunciations[0]]
    return _compose(parts) if all(parts) else None


@lru_cache(maxsize=1024)
def _espeak_word(word: str) -> str | None:
    try:
        completed = subprocess.run(
            ["espeak-ng", "-q", "--ipa=3", "-v", "en-us", word],
            capture_output=True, text=True, timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    ipa = re.sub(r"[ˈˌ.\s]", "", completed.stdout)
    if not ipa:
        return None
    parts: list[str] = []
    index = 0
    while index < len(ipa):
        for phoneme, sinhala in _IPA:
            if ipa.startswith(phoneme, index):
                parts.append(sinhala)
                index += len(phoneme)
                break
        else:
            return None
    return _compose(parts)


def convert_english_to_sinhala(text: str) -> tuple[str | None, str | None]:
    """Convert a word/phrase with CMUdict first, then eSpeak NG.

    A phrase is converted word-by-word so each failure remains safe and does
    not prevent a later known word from using its pronunciation source.
    """
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]*", text)
    if not words:
        return None, None
    converted: list[str] = []
    sources: set[str] = set()
    for word in words:
        value = _cmudict_word(word)
        source = "cmudict" if value else None
        if not value:
            value = _espeak_word(word)
            source = "espeak" if value else None
        if not value:
            return None, None
        converted.append(value)
        sources.add(source)
    return " ".join(converted), "+".join(sorted(sources))
