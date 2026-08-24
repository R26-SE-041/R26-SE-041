"""Deterministic quality gates for anatomy label localization."""

from __future__ import annotations

import math
from typing import Any


MIN_LOCALIZATION_CONFIDENCE = 0.82
MAX_BBOX_IOU = 0.72
MIN_ANCHOR_SEPARATION = 0.035
# Reject proposals whose bounding box is trivially small (likely noise/guess)
# or covers essentially the whole image (not a specific structure).
MIN_BBOX_AREA = 0.0015   # ~0.15% of image area
MAX_BBOX_AREA = 0.65     # 65% of image area
# Reject anchors that land very close to image edges — these are almost always
# background pixels, not foreground anatomy.
EDGE_MARGIN = 0.02       # 2% from any edge


def _bbox_iou(first: list[float], second: list[float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _bbox_area(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _anchor_near_edge(x: float, y: float, margin: float = EDGE_MARGIN) -> bool:
    """Return True when the anchor is within `margin` of any image boundary."""
    return x < margin or x > 1.0 - margin or y < margin or y > 1.0 - margin


def filter_localizations(
    annotations: list[dict[str, Any]],
    *,
    minimum_confidence: float = MIN_LOCALIZATION_CONFIDENCE,
) -> list[dict[str, Any]]:
    """Keep only credible, distinct anchors and mark every returned item verified.

    A VLM can confidently repeat one salient region for several requested anatomy
    terms. Those collisions are unsafe for educational labels, so the strongest
    proposal wins and the ambiguous proposals are omitted.
    """
    candidates: list[tuple[int, dict[str, Any]]] = []
    for index, source in enumerate(annotations):
        try:
            confidence = float(source.get("confidence", 0.0))
            anchor_x = float(source["anchor_x"])
            anchor_y = float(source["anchor_y"])
            bbox = [float(value) for value in source["bbox"]]
        except (KeyError, TypeError, ValueError):
            continue
        if (
            confidence < minimum_confidence
            or len(bbox) != 4
            or not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in [anchor_x, anchor_y, *bbox])
            or bbox[2] <= bbox[0]
            or bbox[3] <= bbox[1]
        ):
            continue
        area = _bbox_area(bbox)
        if area < MIN_BBOX_AREA or area > MAX_BBOX_AREA:
            continue
        if _anchor_near_edge(anchor_x, anchor_y):
            continue
        item = dict(source)
        item.update({"anchor_x": anchor_x, "anchor_y": anchor_y, "bbox": bbox, "confidence": confidence})
        candidates.append((index, item))

    accepted: list[tuple[int, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for index, item in sorted(candidates, key=lambda pair: (-pair[1]["confidence"], pair[0])):
        structure_id = str(item.get("structure_id") or "")
        if not structure_id or structure_id in seen_ids:
            continue
        collides = any(
            math.hypot(item["anchor_x"] - other["anchor_x"], item["anchor_y"] - other["anchor_y"])
            < MIN_ANCHOR_SEPARATION
            or _bbox_iou(item["bbox"], other["bbox"]) > MAX_BBOX_IOU
            for _, other in accepted
        )
        if collides:
            continue
        item["verified"] = True
        accepted.append((index, item))
        seen_ids.add(structure_id)

    return [item for _, item in sorted(accepted, key=lambda pair: pair[0])]

