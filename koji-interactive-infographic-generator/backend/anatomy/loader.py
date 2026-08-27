"""Load and validate organ knowledge without embedding anatomy facts in code."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


ANATOMY_ROOT = Path(__file__).resolve().parent
RESERVED_DIRECTORIES = {"schemas", "__pycache__"}
GRADE_LEVELS = {"primary_school", "middle_school", "high_school", "undergraduate", "general_audience"}
DETAIL_LEVELS = {"basic", "intermediate", "advanced"}
ORIENTATIONS = {"square", "portrait", "landscape"}
VIEW_INTENT = re.compile(
    r"\b(?:view|viewed|side|surface|section|cross[- ]?section|cutaway|cut[- ]?open|"
    r"anterior|posterior|front|back|backside|rear|top|bottom|upper|lower|above|below|"
    r"superior|inferior|dorsal|ventral|lateral|medial|sagittal|coronal|frontal|"
    r"transverse|axial|longitudinal|oblique|internal|external|inside|outside|underside)\b",
    re.I,
)
ANATOMICAL_VIEW_PHRASE = re.compile(
    r"\b(?:"
    r"(?:(?:oblique|direct|slightly)\s+)?"
    r"(?:anterior|posterior|lateral|medial|superior|inferior|dorsal|ventral|"
    r"sagittal|coronal|frontal|transverse|axial|longitudinal|internal|external|"
    r"front|back|rear|top|bottom|upper|lower)"
    r"(?:[- ](?:cross[- ]?section(?:al)?|cutaway|section))?"
    r"(?:\s+(?:view|surface|section|cutaway|side))?"
    r"(?:\s+from\s+(?:above|below|the\s+left|the\s+right))?"
    r"|(?:cross[- ]?section(?:al)?|cutaway|cut[- ]?open)"
    r"(?:\s+(?:view|section))?"
    r")\b",
    re.I,
)
COMPACT_VIEW_ALIASES = (
    (re.compile(r"\bcross\s*view\b", re.I), "lateral cross-sectional cutaway view"),
    (re.compile(r"\bcrosssection(?:al)?\b", re.I), "lateral cross-sectional cutaway view"),
    (re.compile(r"\bside\s*view\b", re.I), "lateral view"),
    (re.compile(r"\binside\s*view\b|\binterior\s*view\b", re.I), "internal cutaway view"),
    (re.compile(r"\bfront\s*view\b", re.I), "anterior view"),
    (re.compile(r"\bback\s*view\b|\bbackside\s*view\b", re.I), "posterior view"),
    (re.compile(r"\btop\s*view\b", re.I), "superior view"),
    (re.compile(r"\bbottom\s*view\b", re.I), "inferior view"),
)
GRADE_DEFAULT_DETAIL = {
    "primary_school": "basic",
    "middle_school": "intermediate",
    "high_school": "intermediate",
    "undergraduate": "advanced",
    "general_audience": "intermediate",
}
GRADE_ALLOWED_DETAIL = {
    "primary_school": {"basic"},
    "middle_school": {"basic", "intermediate"},
    "high_school": {"basic", "intermediate", "advanced"},
    "undergraduate": {"intermediate", "advanced"},
    "general_audience": {"basic", "intermediate"},
}


class AnatomyKnowledgeError(ValueError):
    """Raised when curated anatomy data is missing or internally inconsistent."""


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise AnatomyKnowledgeError(f"Missing anatomy file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise AnatomyKnowledgeError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AnatomyKnowledgeError(f"Anatomy file must contain an object: {path}")
    return payload


def list_supported_organs() -> list[str]:
    return sorted(
        path.name
        for path in ANATOMY_ROOT.iterdir()
        if path.is_dir()
        and path.name not in RESERVED_DIRECTORIES
        and (path / "structures.json").is_file()
    )


@lru_cache(maxsize=1)
def _load_general_defaults() -> dict[str, Any]:
    return _read_json(ANATOMY_ROOT / "general_defaults.json")


def get_general_required_structures(subject: str) -> list[str]:
    """Return reviewed fallback structures for an uncatalogued anatomy subject."""
    entry = _load_general_defaults().get(_normalize(subject))
    if not isinstance(entry, dict) or not isinstance(entry.get("required_structures"), list):
        return []
    return [str(value) for value in entry["required_structures"][:8] if str(value).strip()]


def detect_supported_organ(text: str) -> str | None:
    """Conservatively route explicit supported-organ requests."""
    normalized = f" {_normalize(text).replace('_', ' ')} "
    for organ in list_supported_organs():
        metadata = _read_json(ANATOMY_ROOT / organ / "structures.json")
        aliases = [organ.replace("_", " "), *(metadata.get("aliases") or [])]
        candidates = {f" {_normalize(str(alias)).replace('_', ' ')} " for alias in aliases}
        if any(candidate in normalized for candidate in candidates):
            return organ
    structure_matches = [
        organ for organ in list_supported_organs()
        if detect_requested_structures(organ, text)
    ]
    if len(structure_matches) == 1:
        return structure_matches[0]
    return None


def detect_requested_structures(organ: str, text: str) -> list[str]:
    """Return canonical IDs explicitly named by the user, in catalog order."""
    normalized_text = f" {_normalize(text).replace('_', ' ')} "
    matches: list[str] = []
    for structure in load_organ(organ)["structures"]["structures"]:
        aliases = [structure["id"], structure["label"], *(structure.get("aliases") or [])]
        phrases = {
            f" {_normalize(str(alias)).replace('_', ' ')} "
            for alias in aliases
            if _normalize(str(alias))
        }
        if any(phrase in normalized_text for phrase in phrases):
            matches.append(str(structure["id"]))
    return matches


def preserve_requested_view(text: str) -> str:
    """Preserve open-ended user view wording when spatial intent is explicit."""
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:240] if VIEW_INTENT.search(clean) else ""


def extract_requested_view(text: str) -> str:
    """Return only the concise anatomical view phrase from a larger request."""
    clean = re.sub(r"\s+", " ", text).strip()
    for alias, canonical in COMPACT_VIEW_ALIASES:
        if alias.search(clean):
            return canonical
    match = ANATOMICAL_VIEW_PHRASE.search(clean)
    return match.group(0).strip()[:120] if match else ""


@lru_cache(maxsize=32)
def _load_organ_cached(organ: str) -> dict[str, Any]:
    organ_id = _normalize(organ)
    organ_dir = ANATOMY_ROOT / organ_id
    if organ_id not in list_supported_organs():
        raise AnatomyKnowledgeError(
            f"Unsupported anatomy organ '{organ}'. Supported: {', '.join(list_supported_organs()) or 'none'}"
        )
    payload = {
        "organ": organ_id,
        "structures": _read_json(organ_dir / "structures.json"),
        "relations": _read_json(organ_dir / "relations.json"),
        "views": _read_json(organ_dir / "views.json"),
        "sources": _read_json(organ_dir / "sources.json"),
    }
    _validate_organ(payload)
    return payload


def load_organ(organ: str) -> dict[str, Any]:
    """Return a defensive copy so request code cannot mutate the cache."""
    return deepcopy(_load_organ_cached(organ))


def _validate_organ(payload: dict[str, Any]) -> None:
    organ = payload["organ"]
    structures = payload["structures"].get("structures")
    relations = payload["relations"].get("relations")
    views = payload["views"].get("views")
    sources = payload["sources"].get("sources")
    if not all(isinstance(value, list) for value in (structures, relations, views, sources)):
        raise AnatomyKnowledgeError(f"{organ}: structures, relations, views, and sources must be lists")

    structure_ids = [str(item.get("id") or "") for item in structures]
    if any(not value for value in structure_ids) or len(structure_ids) != len(set(structure_ids)):
        raise AnatomyKnowledgeError(f"{organ}: structure IDs must be non-empty and unique")
    known_structures = set(structure_ids)
    aliases = payload["structures"].get("aliases")
    if not isinstance(aliases, list) or not aliases or any(not str(item).strip() for item in aliases):
        raise AnatomyKnowledgeError(f"{organ}: structures.json requires non-empty organ aliases")

    structure_aliases: dict[str, str] = {}
    for structure in structures:
        if not str(structure.get("label") or "").strip():
            raise AnatomyKnowledgeError(f"{organ}.{structure.get('id')}: label is required")
        for raw_alias in [structure["id"], structure["label"], *(structure.get("aliases") or [])]:
            normalized = _normalize(str(raw_alias))
            previous = structure_aliases.get(normalized)
            if previous and previous != structure["id"]:
                raise AnatomyKnowledgeError(f"{organ}: alias '{raw_alias}' maps to multiple structures")
            structure_aliases[normalized] = structure["id"]

    for relation in relations:
        source = relation.get("source")
        target = relation.get("target")
        if source not in known_structures or target not in known_structures:
            raise AnatomyKnowledgeError(f"{organ}: broken relation {source!r} -> {target!r}")
        if not str(relation.get("relation") or "").strip():
            raise AnatomyKnowledgeError(f"{organ}: relation type is required")

    view_ids: set[str] = set()
    for view in views:
        view_id = str(view.get("id") or "")
        if not view_id or view_id in view_ids:
            raise AnatomyKnowledgeError(f"{organ}: view IDs must be non-empty and unique")
        view_ids.add(view_id)
        referenced = set(view.get("required_structures") or []) | set(view.get("optional_structures") or [])
        unknown = referenced - known_structures
        if unknown:
            raise AnatomyKnowledgeError(f"{organ}.{view_id}: unknown structures {sorted(unknown)}")
        allowed_details = set(view.get("allowed_detail_levels") or DETAIL_LEVELS)
        if not allowed_details or not allowed_details.issubset(DETAIL_LEVELS):
            raise AnatomyKnowledgeError(f"{organ}.{view_id}: invalid allowed_detail_levels")
        default_orientation = view.get("default_orientation", "portrait")
        if default_orientation not in ORIENTATIONS:
            raise AnatomyKnowledgeError(f"{organ}.{view_id}: invalid default_orientation")

    source_ids = [str(item.get("id") or "") for item in sources]
    if not source_ids or any(not value for value in source_ids) or len(source_ids) != len(set(source_ids)):
        raise AnatomyKnowledgeError(f"{organ}: at least one uniquely identified source is required")
    known_sources = set(source_ids)
    for structure in structures:
        citations = set(structure.get("source_ids") or [])
        if not citations:
            raise AnatomyKnowledgeError(f"{organ}.{structure['id']}: at least one source_id is required")
        unknown_sources = citations - known_sources
        if unknown_sources:
            raise AnatomyKnowledgeError(
                f"{organ}.{structure['id']}: unknown source IDs {sorted(unknown_sources)}"
            )


def get_structure(organ: str, structure_id: str) -> dict[str, Any]:
    canonical = canonicalize_structure(organ, structure_id)
    if not canonical:
        raise AnatomyKnowledgeError(f"Unknown structure '{structure_id}' for organ '{organ}'")
    for item in load_organ(organ)["structures"]["structures"]:
        if item["id"] == canonical:
            return item
    raise AnatomyKnowledgeError(f"Unknown structure '{structure_id}' for organ '{organ}'")


def canonicalize_structure(organ: str, value: str) -> str | None:
    normalized = _normalize(value.removeprefix(f"{_normalize(organ)}."))
    for item in load_organ(organ)["structures"]["structures"]:
        candidates = [item["id"], item["label"], *(item.get("aliases") or [])]
        if normalized in {_normalize(str(candidate)) for candidate in candidates}:
            return str(item["id"])
    return None


def get_view(organ: str, view_id: str) -> dict[str, Any]:
    normalized = _normalize(view_id)
    for item in load_organ(organ)["views"]["views"]:
        if _normalize(str(item["id"])) == normalized or normalized in {
            _normalize(str(alias)) for alias in item.get("aliases", [])
        }:
            return item
    raise AnatomyKnowledgeError(f"Unknown view '{view_id}' for organ '{organ}'")


def select_anatomy_view(organ: str, requested_view: str = "") -> dict[str, Any]:
    """Select the closest catalog view, falling back to the organ default."""
    knowledge = load_organ(organ)
    request_id = _normalize(requested_view)
    if request_id:
        for view in knowledge["views"]["views"]:
            candidates = [view["id"], view["label"], *(view.get("aliases") or [])]
            for candidate in candidates:
                candidate_id = _normalize(str(candidate))
                if candidate_id and (candidate_id in request_id or request_id in candidate_id):
                    return view
    return get_view(organ, knowledge["views"]["default_view"])


def validate_anatomy_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Normalize an LLM-produced anatomy spec against curated identifiers."""
    if not spec.get("is_anatomy"):
        return {"is_anatomy": False}
    organ = _normalize(str(spec.get("organ") or ""))
    knowledge = load_organ(organ)
    view = get_view(organ, str(spec.get("view") or knowledge["views"]["default_view"]))
    view_description = re.sub(r"\s+", " ", str(spec.get("view_description") or "")).strip()[:240]
    visible = set(view.get("required_structures") or []) | set(view.get("optional_structures") or [])

    def canonicalize_many(values: Any, field: str) -> list[str]:
        if not isinstance(values, list):
            raise AnatomyKnowledgeError(f"{field} must be a list")
        canonical: list[str] = []
        unknown: list[str] = []
        for value in values:
            structure_id = canonicalize_structure(organ, str(value))
            if structure_id and structure_id not in canonical:
                canonical.append(structure_id)
            elif not structure_id:
                unknown.append(str(value))
        if unknown:
            raise AnatomyKnowledgeError(f"Unknown {organ} structures in {field}: {', '.join(unknown)}")
        incompatible = set(canonical) - visible if not view_description else set()
        if incompatible:
            raise AnatomyKnowledgeError(
                f"Structures not visible in {organ}.{view['id']}: {', '.join(sorted(incompatible))}"
            )
        return canonical

    requested = spec.get("required_structures") or view.get("required_structures") or []
    canonical = canonicalize_many(requested, "required_structures")
    if not canonical:
        raise AnatomyKnowledgeError("An anatomy specification requires at least one structure")
    focus = canonicalize_many(spec.get("focus_structures") or [], "focus_structures")
    outside_required = set(focus) - set(canonical)
    if outside_required:
        raise AnatomyKnowledgeError(
            f"focus_structures must be included in required_structures: {', '.join(sorted(outside_required))}"
        )

    grade_level = _normalize(str(spec.get("grade_level") or "middle_school"))
    if grade_level not in GRADE_LEVELS:
        raise AnatomyKnowledgeError(f"Unsupported grade_level '{spec.get('grade_level')}'")
    detail_level = _normalize(str(spec.get("detail_level") or GRADE_DEFAULT_DETAIL[grade_level]))
    if detail_level not in DETAIL_LEVELS:
        raise AnatomyKnowledgeError(f"Unsupported detail_level '{spec.get('detail_level')}'")
    view_allowed_details = set(view.get("allowed_detail_levels") or DETAIL_LEVELS)
    if detail_level not in GRADE_ALLOWED_DETAIL[grade_level] or detail_level not in view_allowed_details:
        raise AnatomyKnowledgeError(f"detail_level '{detail_level}' is incompatible with grade/view")
    orientation = _normalize(str(spec.get("orientation") or view.get("default_orientation") or "portrait"))
    if orientation not in ORIENTATIONS:
        raise AnatomyKnowledgeError(f"Unsupported orientation '{spec.get('orientation')}'")
    return {
        "is_anatomy": True,
        "organ": organ,
        "view": view["id"],
        "view_description": view_description,
        "grade_level": grade_level,
        "required_structures": canonical,
        "focus_structures": focus,
        "detail_level": detail_level,
        "orientation": orientation,
        "show_flow": bool(spec.get("show_flow", spec.get("show_blood_flow", False))),
        "orientation_note": view.get("orientation_note"),
        "knowledge_version": knowledge["structures"].get("version", "1.0"),
    }
