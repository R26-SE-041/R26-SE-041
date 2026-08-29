"""Geometry helpers for grid-first SAM segmentation and SVG localization."""

from __future__ import annotations

from typing import Any


GRID_SIZE = 6
INNER_START = 1
INNER_END = GRID_SIZE - 1
MIN_MASK_AREA = 0.0015
MAX_MASK_AREA = 0.65
DEDUPLICATION_IOU = 0.80


def inner_grid_points() -> list[dict[str, Any]]:
    """Return the centres of the inner 4x4 cells in a normalized 6x6 grid."""
    return [
        {
            "grid_index": (row - INNER_START) * 4 + (column - INNER_START),
            "grid_row": row,
            "grid_column": column,
            "x": (column + 0.5) / GRID_SIZE,
            "y": (row + 0.5) / GRID_SIZE,
        }
        for row in range(INNER_START, INNER_END)
        for column in range(INNER_START, INNER_END)
    ]


def bbox_area(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def bbox_iou(first: list[float], second: list[float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = bbox_area(first) + bbox_area(second) - intersection
    return intersection / union if union > 0 else 0.0


def keep_unique_masks(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Discard empty/extreme masks and repeated SAM masks from nearby prompts."""
    accepted: list[dict[str, Any]] = []
    for candidate in candidates:
        bbox = candidate.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            clean_bbox = [max(0.0, min(1.0, float(value))) for value in bbox]
        except (TypeError, ValueError):
            continue
        if clean_bbox[2] <= clean_bbox[0] or clean_bbox[3] <= clean_bbox[1]:
            continue
        area = bbox_area(clean_bbox)
        if area < MIN_MASK_AREA or area > MAX_MASK_AREA:
            continue
        if any(bbox_iou(clean_bbox, item["bbox"]) >= DEDUPLICATION_IOU for item in accepted):
            continue
        item = dict(candidate)
        item["bbox"] = clean_bbox
        accepted.append(item)
    return accepted
