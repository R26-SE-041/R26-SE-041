import unittest

from anatomy.enrichment import (
    merge_general_anatomy_enrichment,
    missing_general_anatomy_fields,
)
from anatomy.schema_builder import build_general_anatomy_schema


class GeneralAnatomyEnrichmentTests(unittest.TestCase):
    def test_detects_empty_enrichment_fields(self) -> None:
        spec = {"view_description": "", "required_structures": [], "focus_structures": []}
        self.assertEqual(
            missing_general_anatomy_fields(spec),
            ["view_description", "required_structures", "focus_structures"],
        )

    def test_fills_only_missing_values_and_preserves_existing_values(self) -> None:
        original = {
            "view_description": "anterior cutaway view",
            "required_structures": [],
            "focus_structures": [],
        }
        generated = {
            "view_description": "posterior view",
            "required_structures": ["duodenum", "jejunum", "ileum", "duodenum"],
            "focus_structures": ["ileum"],
        }
        merged, fields = merge_general_anatomy_enrichment(original, generated)
        self.assertEqual(merged["view_description"], "anterior cutaway view")
        self.assertEqual(merged["required_structures"], ["duodenum", "jejunum", "ileum"])
        self.assertEqual(merged["focus_structures"], ["ileum"])
        self.assertEqual(fields, ["required_structures", "focus_structures"])

    def test_focus_is_added_to_required_for_downstream_validation(self) -> None:
        spec = {
            "view_description": "anterior view",
            "required_structures": ["duodenum"],
            "focus_structures": ["ileum"],
        }
        merged, _ = merge_general_anatomy_enrichment(spec, spec)
        self.assertEqual(merged["required_structures"], ["duodenum", "ileum"])

    def test_general_schema_rejects_empty_model_fields(self) -> None:
        properties = build_general_anatomy_schema()["properties"]["anatomy_spec"]["properties"]
        self.assertEqual(properties["view_description"]["minLength"], 1)
        self.assertEqual(properties["required_structures"]["minItems"], 1)
        self.assertEqual(properties["focus_structures"]["minItems"], 1)


if __name__ == "__main__":
    unittest.main()
