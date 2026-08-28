from __future__ import annotations

import unittest

from anatomy import (
    build_anatomy_prompt,
    detect_supported_organ,
    preserve_requested_view,
    validate_anatomy_spec,
)
from shared.prompt_enhancement import ensure_useful_enhancement


class PromptEnhancementTests(unittest.TestCase):
    def test_short_unchanged_prompt_gets_concise_visual_direction(self) -> None:
        enhanced = ensure_useful_enhancement("top side of eye for a biology student", "top side of eye for a biology student")
        self.assertIn("top side of eye for a biology student", enhanced)
        self.assertIn("Preserve the requested subject, viewpoint, and audience", enhanced)
        self.assertLess(len(enhanced.split()), 55)

    def test_useful_model_enhancement_is_not_rewritten(self) -> None:
        candidate = "A clear classroom illustration of photosynthesis showing leaves, sunlight, water, and carbon dioxide in a balanced composition."
        self.assertEqual(ensure_useful_enhancement("photosynthesis", candidate), candidate)

    # ── Regression: view preservation ─────────────────────────────────────────

    def test_brain_gets_sensible_default_view(self) -> None:
        """A bare 'brain' prompt should detect the organ and use the catalog default."""
        organ = detect_supported_organ("brain")
        self.assertEqual(organ, "brain")
        # No explicit view → preserve_requested_view returns empty string
        self.assertEqual(preserve_requested_view("brain"), "")

    def test_posterior_heart_view_is_preserved(self) -> None:
        raw = "posterior view of the heart for a biology student"
        organ = detect_supported_organ(raw)
        self.assertEqual(organ, "heart")
        view_desc = preserve_requested_view(raw)
        self.assertIn("posterior", view_desc.lower())
        # Build an anatomy spec with the view description
        spec = validate_anatomy_spec({
            "is_anatomy": True,
            "organ": "heart",
            "view_description": view_desc,
            "required_structures": ["aorta", "left_atrium"],
        })
        prompt = build_anatomy_prompt(spec)
        self.assertIn("posterior", prompt.lower())
        # Must NOT contain the default "Anterior cutaway" as the primary view
        self.assertNotIn("Anterior cutaway illustration", prompt)

    def test_cross_section_brain_view_is_preserved(self) -> None:
        raw = "cross section view of brain for a biology student"
        organ = detect_supported_organ(raw)
        self.assertEqual(organ, "brain")
        view_desc = preserve_requested_view(raw)
        self.assertIn("cross section", view_desc.lower())
        spec = validate_anatomy_spec({
            "is_anatomy": True,
            "organ": "brain",
            "view_description": view_desc,
            "required_structures": ["cerebrum", "cerebellum"],
        })
        prompt = build_anatomy_prompt(spec)
        self.assertIn("cross section", prompt.lower())

    def test_top_side_eye_not_in_catalog(self) -> None:
        """Eye is not in the catalog — should go through generic enhancement."""
        raw = "top side of eye for a biology student"
        organ = detect_supported_organ(raw)
        self.assertIsNone(organ)
        # Generic path: ensure_useful_enhancement should produce a useful prompt
        enhanced = ensure_useful_enhancement(raw, raw)
        self.assertIn("top side of eye for a biology student", enhanced)
        self.assertIn("educational", enhanced.lower())

    def test_explicit_structure_request_is_preserved(self) -> None:
        """When the user explicitly requests structures, those must survive
        through validation."""
        spec = validate_anatomy_spec({
            "is_anatomy": True,
            "organ": "heart",
            "required_structures": ["aorta", "right_ventricle"],
            "focus_structures": ["aorta", "right_ventricle"],
        })
        self.assertEqual(spec["required_structures"], ["aorta", "right_ventricle"])
        self.assertEqual(spec["focus_structures"], ["aorta", "right_ventricle"])

    def test_no_view_specified_uses_catalog_default(self) -> None:
        """When no view is specified, the catalog default should be used."""
        spec = validate_anatomy_spec({
            "is_anatomy": True,
            "organ": "heart",
            "required_structures": ["aorta"],
        })
        self.assertEqual(spec["view"], "anterior_cutaway")
        self.assertEqual(spec["view_description"], "")
        prompt = build_anatomy_prompt(spec)
        self.assertIn("Anterior cutaway", prompt)

    def test_view_description_overrides_catalog_default_in_prompt(self) -> None:
        """A non-empty view_description must take precedence over the catalog
        reference view in the final FLUX prompt."""
        spec = validate_anatomy_spec({
            "is_anatomy": True,
            "organ": "heart",
            "view_description": "oblique posterior view from above",
            "required_structures": ["aorta", "left_atrium"],
        })
        prompt = build_anatomy_prompt(spec)
        self.assertIn("oblique posterior view from above", prompt)
        # The catalog view label should NOT appear as the primary view phrase
        self.assertNotIn("Anterior cutaway illustration", prompt)


if __name__ == "__main__":
    unittest.main()
