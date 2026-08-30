"""Marker-grounded grid assets and strict validation for automatic anatomy labels."""
from __future__ import annotations

import io
import re
from typing import Any
from PIL import Image, ImageDraw

GRID_SIZE = 6
INNER_START = 1
INNER_END = 5
MIN_CONFIDENCE = 0.82
MAX_LABELS = 8
CONTEXT_SCALE = 0.42
_INVALID_LABEL = re.compile(
    r"\b(?:unknown|unidentified|unclear|background|not sure|cannot|can't|unable|"
    r"possibly|probably|likely|appears|image|region|structure)\b", re.I,
)


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_regions(image_size: tuple[int, int]) -> list[dict[str, Any]]:
    """Build 16 target points plus overlapping context windows.

    The target is the centre of each inner cell in a 6x6 grid. The outer ring
    of 20 cells is skipped because it is normally background. The larger
    context window prevents structures from being cut at cell boundaries.
    """
    width, height = image_size
    if width < GRID_SIZE or height < GRID_SIZE:
        raise ValueError("Image is too small for a 6x6 grid")
    regions: list[dict[str, Any]] = []
    for row in range(INNER_START, INNER_END):
        for column in range(INNER_START, INNER_END):
            bbox = (
                round(column * width / GRID_SIZE), round(row * height / GRID_SIZE),
                round((column + 1) * width / GRID_SIZE), round((row + 1) * height / GRID_SIZE),
            )
            anchor_x = (bbox[0] + bbox[2]) // 2
            anchor_y = (bbox[1] + bbox[3]) // 2
            context_width = max(1, round(width * CONTEXT_SCALE))
            context_height = max(1, round(height * CONTEXT_SCALE))
            context_left = max(0, min(width - context_width, anchor_x - context_width // 2))
            context_top = max(0, min(height - context_height, anchor_y - context_height // 2))
            regions.append({
                "region_id": f"R{len(regions) + 1}",
                "row": row - INNER_START,
                "column": column - INNER_START,
                "bbox_px": bbox,
                "anchor_px": (anchor_x, anchor_y),
                "context_bbox_px": (
                    context_left,
                    context_top,
                    context_left + context_width,
                    context_top + context_height,
                ),
            })
    return regions


def _marked_context_crop(image: Image.Image, region: dict[str, Any]) -> bytes:
    """Crop useful context and draw a ring around, not over, the target pixel."""
    left, top, _, _ = region["context_bbox_px"]
    anchor_x, anchor_y = region["anchor_px"]
    crop = image.crop(region["context_bbox_px"])
    target_x, target_y = anchor_x - left, anchor_y - top
    marker_radius = max(8, round(min(crop.size) * 0.045))
    marker_width = max(3, round(marker_radius * 0.28))
    draw = ImageDraw.Draw(crop)
    # A double ring stays legible on both light and dark anatomy without
    # covering the pixels at the exact target point.
    for radius, color, width_value in (
        (marker_radius + marker_width, "white", marker_width + 2),
        (marker_radius, "#00bcd4", marker_width),
    ):
        draw.ellipse(
            (target_x - radius, target_y - radius, target_x + radius, target_y + radius),
            outline=color,
            width=width_value,
        )
    return _png_bytes(crop)


def build_auto_label_assets(image_bytes: bytes) -> dict[str, Any]:
    """Return the full image and 16 marker-grounded context crops."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    regions = build_regions(image.size)
    return {
        "image_size": image.size,
        "regions": regions,
        "original_bytes": _png_bytes(image),
        "crop_bytes": [_marked_context_crop(image, region) for region in regions],
    }


def _clean_label(value: Any) -> str | None:
    label = re.sub(r"\s+", " ", str(value or "")).strip(" #*-:.,;")[:80]
    if (len(label) < 2 or len(label.split()) > 8
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 .()'/-]*", label)
            or _INVALID_LABEL.search(label)):
        return None
    return label


def validate_auto_labels(
    payload: dict[str, Any] | None, regions: list[dict[str, Any]], image_size: tuple[int, int],
    *, min_confidence: float = MIN_CONFIDENCE, max_labels: int = MAX_LABELS,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Accept supported labels and anchor every pointer at its fixed cell centre."""
    region_map = {item["region_id"]: item for item in regions}
    raw_items = payload.get("regions") if isinstance(payload, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []
    diagnostics = {"candidate_regions": len(regions), "qwen_regions": len(raw_items), "accepted_labels": 0,
                   "rejected_low_confidence": 0, "rejected_invalid": 0, "rejected_duplicate": 0}
    width, height = image_size
    candidates: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict) or item.get("region_id") not in region_map or item.get("visible") is not True:
            diagnostics["rejected_invalid"] += 1
            continue
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            diagnostics["rejected_invalid"] += 1
            continue
        if confidence < min_confidence:
            diagnostics["rejected_low_confidence"] += 1
            continue
        label = _clean_label(item.get("label"))
        if not label:
            diagnostics["rejected_invalid"] += 1
            continue
        region = region_map[item["region_id"]]
        left, top, right, bottom = region["bbox_px"]
        anchor_x, anchor_y = region["anchor_px"]
        candidates.append({
            "structure_id": f"auto.{re.sub(r'[^a-z0-9]+', '_', label.casefold()).strip('_')}",
            "label": label, "anchor_x": anchor_x / width, "anchor_y": anchor_y / height,
            "bbox": [left / width, top / height, right / width, bottom / height], "confidence": confidence,
            "verified": True, "grounding": "marker_grounded_context_crop_qwen_vl", "region_id": item["region_id"],
        })
    best_by_label: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = candidate["label"].casefold()
        existing = best_by_label.get(key)
        if existing is None or candidate["confidence"] > existing["confidence"]:
            if existing is not None:
                diagnostics["rejected_duplicate"] += 1
            best_by_label[key] = candidate
        else:
            diagnostics["rejected_duplicate"] += 1
    for key in list(best_by_label):
        if len(key.split()) != 1:
            continue
        single_region = region_map.get(best_by_label[key]["region_id"])
        if single_region is None:
            continue
        for other_key, other in best_by_label.items():
            if other_key == key or not re.search(rf"\b{re.escape(key)}\b", other_key):
                continue
            other_region = region_map.get(other["region_id"])
            # Only treat this as the same structure when the two labels come from
            # the same or a neighbouring grid cell — two distant structures that
            # merely share a common anatomical word (e.g. "Artery" far from
            # "Coronary artery") are real, separate labels and must both survive.
            if other_region is not None \
                    and abs(single_region["row"] - other_region["row"]) <= 1 \
                    and abs(single_region["column"] - other_region["column"]) <= 1:
                del best_by_label[key]
                diagnostics["rejected_duplicate"] += 1
                break
    accepted = sorted(best_by_label.values(), key=lambda item: item["confidence"], reverse=True)[:max_labels]
    diagnostics["accepted_labels"] = len(accepted)
    return accepted, diagnostics
