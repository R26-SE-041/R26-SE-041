"""Merge model-generated values into incomplete uncatalogued anatomy specs."""

from __future__ import annotations

from typing import Any


ENRICHABLE_FIELDS = ("view_description", "required_structures", "focus_structures")


def missing_general_anatomy_fields(spec: dict[str, Any]) -> list[str]:
    """Return required enrichment fields that are blank or empty."""
    missing: list[str] = []
    if not str(spec.get("view_description") or "").strip():
        missing.append("view_description")
    for field in ("required_structures", "focus_structures"):
        values = spec.get(field)
        if not isinstance(values, list) or not any(str(value).strip() for value in values):
            missing.append(field)
    return missing


def merge_general_anatomy_enrichment(
    original: dict[str, Any], generated: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Fill only missing fields, preserving user/catalog-provided values."""
    merged = dict(original)
    filled: list[str] = []
    for field in missing_general_anatomy_fields(original):
        value = generated.get(field)
        if field == "view_description":
            value = str(value or "").strip()
            if value:
                merged[field] = value
                filled.append(field)
        elif isinstance(value, list):
            clean = list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))[:8]
            if clean:
                merged[field] = clean
                filled.append(field)

    # Focus entries must also be required so the downstream compiler cannot
    # silently discard a useful model-generated focus structure.
    required = list(merged.get("required_structures") or [])
    required_keys = {str(item).casefold() for item in required}
    for focus in merged.get("focus_structures") or []:
        if str(focus).casefold() not in required_keys and len(required) < 8:
            required.append(focus)
            required_keys.add(str(focus).casefold())
    merged["required_structures"] = required
    return merged, filled
