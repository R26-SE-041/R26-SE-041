"""Dependency-free, deterministic metrics for the anatomy pipeline."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Iterable


FORBIDDEN_IMAGE_TEXT = ("label", "caption", "legend", "text", "arrow", "callout")


def _mean(values: Iterable[float]) -> float:
    clean = [float(value) for value in values if value is not None]
    return statistics.fmean(clean) if clean else 0.0


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = max(0.0, min(1.0, quantile)) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def score_prompt(enhanced_prompt: str, anatomy_spec: dict[str, Any]) -> dict[str, float]:
    text = enhanced_prompt.casefold()
    required = [str(value).replace("_", " ").casefold() for value in anatomy_spec.get("required_structures") or []]
    mentioned = sum(1 for value in required if value in text)
    clean_rules = (
        "no embedded text",
        "no labels",
        "light neutral background",
        "empty side margins",
    )
    return {
        "structure_coverage": mentioned / len(required) if required else 1.0,
        "clean_rule_coverage": sum(rule in text for rule in clean_rules) / len(clean_rules),
        "organ_match": float(str(anatomy_spec.get("organ") or "").casefold() in text),
        "view_match": float(str(anatomy_spec.get("view") or "").replace("_", " ").casefold() in text),
    }


def _segments_intersect(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> bool:
    def orientation(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    return orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0


def score_svg_layout(annotations: list[dict[str, Any]], expected_ids: list[str]) -> dict[str, float]:
    expected = set(expected_ids)
    actual = {str(item.get("structure_id") or "").split(".")[-1] for item in annotations}
    verified = [item for item in annotations if item.get("verified")]
    overlaps = 0
    crossings = 0
    for index, first in enumerate(annotations):
        first_box = (float(first.get("label_x", 0)), float(first.get("label_y", 0)))
        for second in annotations[index + 1:]:
            second_box = (float(second.get("label_x", 0)), float(second.get("label_y", 0)))
            if abs(first_box[0] - second_box[0]) < 0.18 and abs(first_box[1] - second_box[1]) < 0.055:
                overlaps += 1
            if _segments_intersect(
                (float(first.get("anchor_x", 0)), float(first.get("anchor_y", 0))), first_box,
                (float(second.get("anchor_x", 0)), float(second.get("anchor_y", 0))), second_box,
            ):
                crossings += 1
    pair_count = len(annotations) * (len(annotations) - 1) / 2
    return {
        "canonical_id_recall": len(expected & actual) / len(expected) if expected else 1.0,
        "verified_rate": len(verified) / len(annotations) if annotations else 0.0,
        "label_overlap_rate": overlaps / pair_count if pair_count else 0.0,
        "leader_crossing_rate": crossings / pair_count if pair_count else 0.0,
        "mean_localization_confidence": _mean(item.get("confidence", 0) for item in annotations),
    }


def aggregate_runs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("variant") or "unknown")].append(row)
    summary: dict[str, Any] = {}
    for variant, items in grouped.items():
        metric_names = sorted({name for item in items for name in (item.get("metrics") or {})})
        latencies = [float(item.get("latency_ms") or 0) for item in items]
        summary[variant] = {
            "runs": len(items),
            "metrics": {name: _mean((item.get("metrics") or {}).get(name, 0) for item in items) for name in metric_names},
            "latency_ms": {"mean": _mean(latencies), "p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95)},
            "hard_failure_rate": _mean(bool(item.get("hard_failures")) for item in items),
        }
    return summary
