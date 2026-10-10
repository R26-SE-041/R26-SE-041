"""Build model-output schemas from the installed anatomy catalog."""

from __future__ import annotations

from typing import Any

from .loader import DETAIL_LEVELS, GRADE_LEVELS, ORIENTATIONS, load_organ


def build_anatomy_extraction_schema(organ: str) -> dict[str, Any]:
    """Constrain Qwen to canonical values for one installed organ bundle."""
    knowledge = load_organ(organ)
    structure_ids = [item["id"] for item in knowledge["structures"]["structures"]]
    view_ids = [item["id"] for item in knowledge["views"]["views"]]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["anatomy_spec"],
        "properties": {
            "anatomy_spec": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "is_anatomy", "organ", "view", "view_description", "grade_level",
                    "required_structures", "focus_structures", "detail_level",
                    "orientation", "show_flow",
                ],
                "properties": {
                    "is_anatomy": {"type": "boolean"},
                    "organ": {"type": "string", "enum": [knowledge["organ"]]},
                    "view": {"type": "string", "enum": view_ids},
                    "view_description": {"type": "string", "maxLength": 240},
                    "grade_level": {"type": "string", "enum": sorted(GRADE_LEVELS)},
                    "required_structures": {
                        "type": "array", "minItems": 1, "maxItems": 8, "uniqueItems": True,
                        "items": {"type": "string", "enum": structure_ids},
                    },
                    "focus_structures": {
                        "type": "array", "maxItems": 8, "uniqueItems": True,
                        "items": {"type": "string", "enum": structure_ids},
                    },
                    "detail_level": {"type": "string", "enum": sorted(DETAIL_LEVELS)},
                    "orientation": {"type": "string", "enum": sorted(ORIENTATIONS)},
                    "show_flow": {"type": "boolean"},
                },
            },
        },
    }


def build_generic_enhancement_schema() -> dict[str, Any]:
    """Constrain non-anatomy enhancement to the public response shape."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["enhanced_prompt", "anatomy_spec"],
        "properties": {
            "enhanced_prompt": {"type": "string", "minLength": 1},
            "anatomy_spec": {
                "type": "object", "additionalProperties": False,
                "required": ["is_anatomy"],
                "properties": {"is_anatomy": {"type": "boolean"}},
            },
        },
    }


def build_general_anatomy_schema() -> dict[str, Any]:
    """Constrain unsupported-organ intent without pretending catalog verification."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["anatomy_spec"],
        "properties": {
            "anatomy_spec": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "is_anatomy", "catalog_verified", "organ", "view_description",
                    "grade_level", "required_structures", "focus_structures", "detail_level", "orientation",
                    "show_flow",
                ],
                "properties": {
                    "is_anatomy": {"type": "boolean", "enum": [True]},
                    "catalog_verified": {"type": "boolean", "enum": [False]},
                    "organ": {"type": "string", "minLength": 1, "maxLength": 80},
                    "view_description": {"type": "string", "minLength": 1, "maxLength": 240},
                    "grade_level": {"type": "string", "enum": sorted(GRADE_LEVELS)},
                    "required_structures": {
                        "type": "array", "minItems": 1, "maxItems": 8, "uniqueItems": True,
                        "items": {"type": "string", "minLength": 1, "maxLength": 80},
                    },
                    "focus_structures": {
                        "type": "array", "minItems": 1, "maxItems": 8, "uniqueItems": True,
                        "items": {"type": "string", "minLength": 1, "maxLength": 80},
                    },
                    "detail_level": {"type": "string", "enum": sorted(DETAIL_LEVELS)},
                    "orientation": {"type": "string", "enum": sorted(ORIENTATIONS)},
                    "show_flow": {"type": "boolean"},
                },
            },
        },
    }
