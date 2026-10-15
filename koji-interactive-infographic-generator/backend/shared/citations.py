"""Attach source names from retrieval metadata, never from model guesses."""
from __future__ import annotations

import re


def answer_body(answer: str) -> str:
    # The model writes inline references; the application owns the bibliography.
    return re.split(r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:sources?|references?)(?:\*\*)?\s*(?::(?:\*\*)?[^\n]*)?\s*$", answer, maxsplit=1)[0].strip()


def cited_sources(answer: str, sources: list[dict]) -> list[dict]:
    cited = {int(value) for value in re.findall(r"\[(\d+)\]", answer_body(answer))}
    available = {source["number"] for source in sources}
    if not cited or not cited <= available:
        return []
    return [source for source in sources if source["number"] in cited]


def source_label(source: dict) -> str:
    label = " ".join(str(source.get("filename") or source.get("title") or "Retrieved reference").split())
    page = source.get("page")
    return label + (f" · PDF page {page}" if isinstance(page, int) and page > 0 else "")


def sourced_answer(answer: str, sources: list[dict], unavailable: str) -> str:
    used = cited_sources(answer, sources)
    if not used:
        return unavailable
    footer = "\n".join(f"[{source['number']}] {source_label(source)}" for source in used)
    return answer_body(answer) + "\n\nSources:\n" + footer
