"""Curated, versioned anatomy knowledge used across the pipeline."""

from .loader import (
    AnatomyKnowledgeError,
    canonicalize_structure,
    detect_requested_structures,
    detect_supported_organ,
    extract_requested_view,
    get_structure,
    get_view,
    list_supported_organs,
    load_organ,
    preserve_requested_view,
    validate_anatomy_spec,
)
from .prompt_builder import (
    build_anatomy_prompt,
    compile_anatomy_prompt,
    compile_any_anatomy_prompt,
    compile_general_anatomy_prompt,
)
from .schema_builder import (
    build_anatomy_extraction_schema,
    build_general_anatomy_schema,
    build_generic_enhancement_schema,
)

__all__ = [
    "AnatomyKnowledgeError",
    "canonicalize_structure",
    "detect_requested_structures",
    "detect_supported_organ",
    "extract_requested_view",
    "get_structure",
    "get_view",
    "list_supported_organs",
    "load_organ",
    "preserve_requested_view",
    "validate_anatomy_spec",
    "build_anatomy_prompt",
    "compile_anatomy_prompt",
    "compile_any_anatomy_prompt",
    "compile_general_anatomy_prompt",
    "build_anatomy_extraction_schema",
    "build_general_anatomy_schema",
    "build_generic_enhancement_schema",
]
