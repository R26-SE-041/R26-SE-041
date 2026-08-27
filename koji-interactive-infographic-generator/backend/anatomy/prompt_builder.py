"""Deterministically turn a validated anatomy spec into a FLUX prompt."""

from __future__ import annotations

import re
from typing import Any

from .loader import (
    DETAIL_LEVELS,
    GRADE_ALLOWED_DETAIL,
    GRADE_DEFAULT_DETAIL,
    GRADE_LEVELS,
    ORIENTATIONS,
    get_structure,
    get_view,
    list_supported_organs,
    load_organ,
    validate_anatomy_spec,
)


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


def compile_anatomy_prompt(spec: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Validate an anatomy specification and compile its canonical FLUX prompt.

    Keeping both operations behind one trust boundary prevents callers from
    accidentally generating from an unvalidated model response.
    """
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
    prompt = ". ".join(part.strip().rstrip(".") for part in parts if part.strip()) + "."
    return validated, prompt


def build_anatomy_prompt(spec: dict[str, Any]) -> str:
    """Backward-compatible prompt-only wrapper around the compiler."""
    return compile_anatomy_prompt(spec)[1]


def _clean_phrase(value: Any, max_length: int) -> str:
    clean = re.sub(r"[^a-zA-Z0-9 ,()'/-]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", clean).strip(" ,-/")[:max_length]


def compile_general_anatomy_prompt(spec: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Compile a conservative label-free prompt for an uncatalogued human organ."""
    if not spec.get("is_anatomy"):
        raise ValueError("A general anatomy prompt requires is_anatomy=true")
    organ = _clean_phrase(spec.get("organ"), 80)
    if not organ:
        raise ValueError("A general anatomy prompt requires an organ or anatomical subject")
    minimal_prompt = bool(spec.get("_minimal_prompt")) or spec.get("prompt_profile") == "minimal"
    view_description = _clean_phrase(spec.get("view_description"), 240)
    grade_level = str(spec.get("grade_level") or "general_audience").strip().lower()
    if grade_level not in GRADE_LEVELS:
        grade_level = "general_audience"
    detail_level = str(spec.get("detail_level") or GRADE_DEFAULT_DETAIL[grade_level]).strip().lower()
    if detail_level not in DETAIL_LEVELS or detail_level not in GRADE_ALLOWED_DETAIL[grade_level]:
        detail_level = GRADE_DEFAULT_DETAIL[grade_level]
    orientation = str(spec.get("orientation") or "portrait").strip().lower()
    if orientation not in ORIENTATIONS:
        orientation = "portrait"
    structures: list[str] = []
    for value in spec.get("required_structures") or []:
        clean = _clean_phrase(value, 80)
        if clean and clean.casefold() not in {item.casefold() for item in structures}:
            structures.append(clean)
        if len(structures) == 8:
            break
    focus_structures: list[str] = []
    required_keys = {item.casefold() for item in structures}
    for value in spec.get("focus_structures") or []:
        clean = _clean_phrase(value, 80)
        if (
            clean
            and clean.casefold() in required_keys
            and clean.casefold() not in {item.casefold() for item in focus_structures}
        ):
            focus_structures.append(clean)
    use_minimal_template = bool(
        minimal_prompt and not view_description and not structures and not spec.get("show_flow", False)
    )
    validated = {
        "is_anatomy": True,
        "catalog_verified": False,
        "organ": organ,
        "view_description": view_description,
        "grade_level": grade_level,
        "required_structures": structures,
        "focus_structures": focus_structures,
        "detail_level": detail_level,
        "orientation": orientation,
        "show_flow": bool(spec.get("show_flow", False)),
        "knowledge_version": "general-anatomy-1.0",
        "prompt_profile": "minimal" if use_minimal_template else "detailed",
    }
    parts = [
        "EDUANAT",
        f"medically accurate educational illustration of one isolated human {organ}",
        f"anatomical viewpoint or section: {view_description}" if view_description else "standard educational anatomical view",
    ]
    if use_minimal_template:
        parts.extend([
            "cross-sectional cutaway medical textbook diagram revealing the internal anatomy and major structures",
            "clearly differentiated anatomical tissues with realistic spatial relationships",
            "centered on a white or very light neutral background",
            "no labels, no text, no arrows, no callouts, no border, no watermark",
        ])
        return validated, ". ".join(part.strip().rstrip(".") for part in parts) + "."
    if structures:
        parts.append(f"show the required visible structures: {', '.join(structures)}")
    if focus_structures:
        parts.append(f"visually emphasize: {', '.join(focus_structures)}")
    if validated["show_flow"]:
        parts.append("use anatomically consistent color differentiation for the requested flow without arrows or text")
    parts.extend([
        f"for {grade_level.replace('_', ' ')} learners",
        DETAIL_INSTRUCTIONS[detail_level],
        ORIENTATION_INSTRUCTIONS[orientation],
        "preserve the requested anatomical direction, section, laterality, and visible surfaces",
        "do not add unrelated organs, torso, or anatomical structures not requested",
        "centered composition with clear anatomical boundaries",
        ", ".join(MANDATORY_CLEAN_RULES),
    ])
    prompt = ". ".join(part.strip().rstrip(".") for part in parts if part.strip()) + "."
    return validated, prompt


def compile_any_anatomy_prompt(spec: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Use catalog validation when available, otherwise the conservative compiler."""
    organ = re.sub(r"[^a-z0-9]+", "_", str(spec.get("organ") or "").casefold()).strip("_")
    if organ in set(list_supported_organs()):
        return compile_anatomy_prompt(spec)
    return compile_general_anatomy_prompt(spec)
