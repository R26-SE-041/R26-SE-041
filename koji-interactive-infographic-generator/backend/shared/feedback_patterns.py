"""Convert recurring interaction behavior into reviewable SKILL rule candidates."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_concept(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip().lower()
    clean = re.sub(r"[^a-z0-9 ()+\-/]", "", clean)
    return clean[:80]


def _pattern(
    concept: str,
    pattern_type: str,
    occurrences: int,
    confidence: float,
    suggested_rule: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    key_source = f"{pattern_type}:{concept}".encode("utf-8")
    return {
        "pattern_key": hashlib.sha256(key_source).hexdigest(),
        "concept": concept,
        "pattern_type": pattern_type,
        "occurrences": occurrences,
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "suggested_rule": suggested_rule,
        "metadata": metadata,
    }


def detect_feedback_patterns(
    aggregates: list[dict[str, Any]],
    rate_threshold: float = 0.50,
) -> list[dict[str, Any]]:
    """Detect clarity, labeling, and pedagogy signals without an LLM."""
    patterns: list[dict[str, Any]] = []
    for row in aggregates:
        concept = normalize_concept(str(row.get("concept") or ""))
        occurrences = int(row.get("occurrences") or 0)
        if not concept or occurrences < 1:
            continue
        identify_rate = int(row.get("identify_count") or 0) / occurrences
        question_rate = int(row.get("question_count") or 0) / occurrences
        metadata = {
            "identify_rate": round(identify_rate, 4),
            "question_rate": round(question_rate, 4),
            "avg_visual_score": _optional_float(row.get("avg_visual_score")),
            "avg_pedagogical_score": _optional_float(row.get("avg_pedagogical_score")),
        }
        evidence_weight = min(1.0, occurrences / 20.0)

        if identify_rate >= rate_threshold:
            patterns.append(_pattern(
                concept, "visual_clarity", occurrences,
                identify_rate * (0.7 + 0.3 * evidence_weight),
                f"When depicting {concept}, make it visually distinct and include a clear nearby label.",
                metadata,
            ))
        if question_rate >= rate_threshold:
            patterns.append(_pattern(
                concept, "missing_explanation", occurrences,
                question_rate * (0.7 + 0.3 * evidence_weight),
                f"For {concept}, show its role or relationship with concise labels and directional cues.",
                metadata,
            ))
        pedagogical = _optional_float(row.get("avg_pedagogical_score"))
        if pedagogical is not None and pedagogical < 7.0:
            patterns.append(_pattern(
                concept, "pedagogical_gap", occurrences,
                ((7.0 - pedagogical) / 7.0) * (0.7 + 0.3 * evidence_weight),
                f"For {concept}, prioritize scientifically accurate structure, terminology, and learner-level detail.",
                metadata,
            ))
    return patterns


def _optional_float(value: Any) -> float | None:
    return round(float(value), 4) if value is not None else None


def analyze_and_store(days: int = 30, min_occurrences: int = 3) -> list[dict[str, Any]]:
    from shared.db import list_interaction_aggregates, upsert_feedback_pattern
    patterns = detect_feedback_patterns(list_interaction_aggregates(days, min_occurrences))
    for pattern in patterns:
        pattern["id"] = upsert_feedback_pattern(pattern)
    return patterns

