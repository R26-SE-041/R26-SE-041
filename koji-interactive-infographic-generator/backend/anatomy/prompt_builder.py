"""Deterministically turn a validated anatomy spec into a FLUX prompt."""

from __future__ import annotations

from typing import Any

from .loader import get_structure, get_view, load_organ, validate_anatomy_spec


DETAIL_INSTRUCTIONS = {
    "basic": "simple, clear anatomy",
    "intermediate": "clear textbook anatomy",
    "advanced": "precise advanced anatomy",
}

ORIENTATION_INSTRUCTIONS = {
    "square": "square composition",
    "portrait": "portrait composition",
    "landscape": "landscape composition",
}

MANDATORY_CLEAN_RULES = (
    "white or very light neutral background",
    "no labels, no text, no arrows, no callouts, no border, no watermark",
)


def _labels(organ: str, structure_ids: list[str]) -> str:
    return ", ".join(get_structure(organ, structure_id)["label"] for structure_id in structure_ids)


def build_anatomy_prompt(spec: dict[str, Any]) -> str:
    """Build a stable prompt. Validation is always repeated at this trust boundary."""
    validated = validate_anatomy_spec(spec)
    if not validated.get("is_anatomy"):
        raise ValueError("An anatomy prompt requires is_anatomy=true")

    organ = validated["organ"]
    knowledge = load_organ(organ)
    view = get_view(organ, validated["view"])
    requested_view = str(validated.get("view_description") or "").strip()
    trigger = str(knowledge["structures"].get("trigger_word") or "").strip()
    required = _labels(organ, validated["required_structures"])
    focus = _labels(organ, validated["focus_structures"])
    clean_rules = list(MANDATORY_CLEAN_RULES)

    parts = [
        trigger,
        (
            f"medically accurate illustration of the human {organ}, anatomical viewpoint or section: {requested_view}"
            if requested_view
            else f"medically accurate {view['label'].casefold()} illustration of the human {organ}"
        ),
    ]
    # For an open-ended custom view, do not force structures selected from the
    # catalog's fallback view into the generated image. Explicit focus requests
    # remain authoritative; other IDs are localization candidates only.
    if not requested_view or focus:
        parts.append(f"show {required}")
    if focus:
        parts.append(f"focus on {focus}")
    if validated["show_flow"]:
        parts.append("use anatomically consistent color differentiation for the requested flow without arrows or text")
    parts.extend([
        f"for {validated['grade_level'].replace('_', ' ')} learners",
        DETAIL_INSTRUCTIONS[validated["detail_level"]],
        (
            "preserve the requested viewpoint, anatomical laterality, depth, and visible-versus-hidden surfaces"
            if requested_view else str(view["orientation_note"])
        ),
        ORIENTATION_INSTRUCTIONS[validated["orientation"]],
        "isolated centered organ with clear boundaries",
        ", ".join(clean_rules),
    ])
    return ". ".join(part.strip().rstrip(".") for part in parts if part.strip()) + "."
