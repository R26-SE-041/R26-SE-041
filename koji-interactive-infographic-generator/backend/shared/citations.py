"""Attach source names from retrieval metadata, never from model guesses."""
from __future__ import annotations

import re


def answer_body(answer: str) -> str:
    # The model writes inline references; the application owns the bibliography.
    return re.split(r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:sources?|references?)(?:\*\*)?\s*(?::(?:\*\*)?[^\n]*)?\s*$", answer, maxsplit=1)[0].strip()


def cited_sources(answer: str, sources: list[dict]) -> list[dict]:
    # Models also use grouped references such as [1, 2]. Validate every
    # number in a group; a valid number must not hide an invented reference.
    groups = re.findall(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]", answer_body(answer))
    cited = {int(value) for group in groups for value in re.findall(r"\d+", group)}
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


def _numbered_heading(text: str) -> bool:
    # Flattened PDF page titles can end with their page/section number.
    words = re.findall(r"[A-Za-z]+",text)
    return bool(re.search(r"\d+\.$",text) and words
                and sum(word[0].isupper() for word in words) > len(words) / 2)


def pdf_answer_schema(sources: list[dict]) -> dict:
    """Require evidence for each point and validate the available source metadata."""
    if not sources or any(not isinstance(s,dict) or type(s.get("number")) is not int
            or s["number"] < 1 or not isinstance(s.get("excerpt"),str) or not s["excerpt"].strip() for s in sources):
        raise ValueError("PDF sources need positive source numbers and readable excerpts")
    options = []
    for source in sources:
        excerpt = " ".join(source["excerpt"].split())
        sentences = re.split(r"(?<=[.!?])\s+|\s*[•●]\s*",excerpt)
        complete = [s.strip() for s in sentences if 8 <= len(s.strip()) <= 300
                    and s.strip().endswith((".","!","?")) and not _numbered_heading(s.strip())]
        if not complete and len(excerpt) >= 8 and not _numbered_heading(excerpt):
            complete = [excerpt if len(excerpt) <= 300 else excerpt[:300].rsplit(" ",1)[0]]
        options.extend(complete)
    options = list(dict.fromkeys(options))
    if not options:
        raise ValueError("PDF excerpts contain no selectable study points")
    return {
        "type":"object", "additionalProperties":False, "required":["points"],
        "properties":{
            "points":{
                "type":"array", "maxItems":8,
                "items":{
                    "type":"object", "additionalProperties":False, "required":["evidence"],
                    "properties":{
                        "evidence":{"type":"string","enum":options},
                    },
                },
            },
        },
    }


def pdf_structured_answer(payload: dict, sources: list[dict]) -> str:
    """Locate model-selected evidence verbatim before assigning its actual source."""
    schema = pdf_answer_schema(sources)
    allowed = set(schema["properties"]["points"]["items"]["properties"]["evidence"]["enum"])
    if not isinstance(payload,dict) or set(payload) != {"points"}:
        raise ValueError("Invalid structured PDF answer")
    points = payload["points"]
    if not isinstance(points,list) or len(points) > 8:
        raise ValueError("Invalid PDF answer fields")
    lines = []
    seen = set()
    for point in points:
        if not isinstance(point,dict) or set(point) != {"evidence"} or not isinstance(point["evidence"],str):
            raise ValueError("Invalid PDF answer point")
        evidence = " ".join(point["evidence"].split())
        if evidence not in allowed:
            raise ValueError("PDF answer selected an unavailable study point")
        matching = [s for s in sources if evidence in " ".join(s.get("excerpt", "").split())]
        if not matching:
            raise ValueError("PDF supporting quote does not occur in the supplied excerpts")
        if evidence not in seen:
            seen.add(evidence)
            lines.append(f"- [{matching[0]['number']}] {evidence}")
    return "Key points from the selected PDF:\n\n" + "\n".join(lines) if lines else "The selected excerpts do not cover this question."
