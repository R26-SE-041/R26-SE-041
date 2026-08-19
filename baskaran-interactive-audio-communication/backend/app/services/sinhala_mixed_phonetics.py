"""TTS-only Sinhala/English phonetic preprocessing for the temporary test route.

This module deliberately has no dependency on RAG, ASR, or production TTS.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.services.sinhala_tts_pronunciation import PRONUNCIATION_DICTIONARY
from app.services.sinhala_english_g2p import convert_english_to_sinhala

logger = get_logger(__name__)
_LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9-]*(?: +[A-Za-z][A-Za-z0-9-]*)*")
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_SINHALA = re.compile(r"[\u0D80-\u0DFF]")
_BAD_OUTPUT = re.compile(r"(?:sinhala|answer|translation|here is|```|:)", re.I)


@dataclass(frozen=True)
class PhoneticSpan:
    original: str
    phonetic: str
    source: str


@dataclass(frozen=True)
class PhoneticResult:
    original: str
    phonetic_text: str
    spans: list[PhoneticSpan]
    warnings: list[str]


def _cache_key(span: str) -> str:
    # Case preserves acronym distinctions: API and Api should not silently share
    # a spelling, while ordinary words normalize safely.
    return span.strip() if span.isupper() else " ".join(span.casefold().split())


class SinhalaPhoneticCache:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE IF NOT EXISTS sinhala_phonetics (cache_key TEXT PRIMARY KEY, phonetic TEXT NOT NULL)")
        return conn

    def get(self, span: str) -> str | None:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT phonetic FROM sinhala_phonetics WHERE cache_key=?", (_cache_key(span),)).fetchone()
            return row[0] if row else None
        except sqlite3.Error as exc:
            logger.warning("Sinhala phonetic cache read failed: %s", exc)
            return None

    def put(self, span: str, phonetic: str) -> None:
        try:
            with self._connect() as conn:
                conn.execute("INSERT OR REPLACE INTO sinhala_phonetics(cache_key, phonetic) VALUES (?, ?)", (_cache_key(span), phonetic))
        except sqlite3.Error as exc:
            logger.warning("Sinhala phonetic cache write failed: %s", exc)


def _valid_phonetic_output(value: str, source: str) -> bool:
    value = value.strip()
    return bool(value and len(value) <= max(80, len(source) * 8) and _SINHALA.search(value) and not _BAD_OUTPUT.search(value))


class SinhalaMixedPhonetics:
    def __init__(self, cache_path: str):
        self.cache = SinhalaPhoneticCache(Path(cache_path))

    async def preprocess(self, text: str) -> PhoneticResult:
        runs = list(_LATIN_RUN.finditer(text))
        if not runs:
            return PhoneticResult(text, text, [], [])

        spans: list[PhoneticSpan] = []
        warnings: list[str] = []
        replacements: list[tuple[int, int, str]] = []
        for run in runs:
            words = list(_LATIN_WORD.finditer(run.group(0)))
            index = 0
            while index < len(words):
                # Curated phrases win over their component words.  If there is
                # no known entry, retain contiguous unknown words for G2P.
                chosen_end = index + 1
                for end in range(len(words), index, -1):
                    candidate = run.group(0)[words[index].start():words[end - 1].end()]
                    if _cache_key(candidate) in PRONUNCIATION_DICTIONARY:
                        chosen_end = end
                        break
                if chosen_end == index + 1 and _cache_key(run.group(0)[words[index].start():words[index].end()]) not in PRONUNCIATION_DICTIONARY:
                    while chosen_end < len(words):
                        next_word = run.group(0)[words[chosen_end].start():words[chosen_end].end()]
                        if _cache_key(next_word) in PRONUNCIATION_DICTIONARY:
                            break
                        chosen_end += 1
                start, end = words[index].start(), words[chosen_end - 1].end()
                original = run.group(0)[start:end]
                index = chosen_end
                key = _cache_key(original)
                phonetic = PRONUNCIATION_DICTIONARY.get(key)
                source = "dictionary"
                if not phonetic:
                    phonetic = self.cache.get(original)
                    source = "cache"
                if not phonetic:
                    candidate, g2p_source = convert_english_to_sinhala(original)
                    if candidate and _valid_phonetic_output(candidate, original):
                        phonetic = candidate
                        self.cache.put(original, phonetic)
                        source = g2p_source or "g2p"
                    else:
                        phonetic = original
                        source = "original"
                        warnings.append(f"No validated Sinhala phonetic rendering for '{original}'.")
                spans.append(PhoneticSpan(original, phonetic, source))
                logger.info("[SINHALA PHONETICS] %r -> [%s]", original, source)
                replacements.append((run.start() + start, run.start() + end, phonetic))

        pieces: list[str] = []
        offset = 0
        for start, end, replacement in replacements:
            pieces.extend((text[offset:start], replacement))
            offset = end
        pieces.append(text[offset:])
        return PhoneticResult(text, "".join(pieces), spans, warnings)

    @staticmethod
    def as_preview(result: PhoneticResult) -> dict:
        return {"original": result.original, "phonetic_text": result.phonetic_text, "spans": [asdict(span) for span in result.spans], "warnings": result.warnings}
