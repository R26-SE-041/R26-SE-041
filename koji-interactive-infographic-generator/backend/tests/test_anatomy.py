from __future__ import annotations

import unittest

from anatomy import (
    AnatomyKnowledgeError,
    build_anatomy_prompt,
    build_anatomy_extraction_schema,
    compile_anatomy_prompt,
    compile_any_anatomy_prompt,
    compile_general_anatomy_prompt,
    canonicalize_structure,
    detect_requested_structures,
    detect_supported_organ,
    extract_requested_view,
    get_view,
    list_supported_organs,
    load_organ,
    preserve_requested_view,
    validate_anatomy_spec,
)


class AnatomyKnowledgeTests(unittest.TestCase):
    def test_heart_bundle_loads(self) -> None:
        knowledge = load_organ("heart")
        self.assertGreaterEqual(len(knowledge["structures"]["structures"]), 12)
        self.assertGreaterEqual(len(knowledge["relations"]["relations"]), 10)

    def test_installed_organ_bundles_load(self) -> None:
        installed = set(list_supported_organs())
        top_five = {"brain", "heart", "kidneys", "liver", "lungs"}
        self.assertTrue(top_five.issubset(installed))
        for organ in installed:
            knowledge = load_organ(organ)
            self.assertGreaterEqual(len(knowledge["structures"]["structures"]), 10)
            self.assertGreaterEqual(len(knowledge["relations"]["relations"]), 10)

    def test_aliases_are_canonicalized(self) -> None:
        self.assertEqual(canonicalize_structure("heart", "right atrium"), "right_atrium")
        self.assertEqual(canonicalize_structure("heart", "heart.aorta"), "aorta")

    def test_prompt_detection_is_conservative(self) -> None:
        self.assertEqual(detect_supported_organ("human cardiac anatomy"), "heart")
        self.assertIsNone(detect_supported_organ("a landscape photograph"))
        self.assertEqual(detect_supported_organ("brain sagittal section"), "brain")
        self.assertEqual(detect_supported_organ("pulmonary lobes"), "lungs")
        self.assertEqual(detect_supported_organ("hepatic anatomy"), "liver")
        self.assertEqual(detect_supported_organ("renal cutaway"), "kidneys")
        self.assertEqual(detect_supported_organ("focus on the right atrium"), "heart")

    def test_explicit_structure_mentions_are_catalog_driven(self) -> None:
        self.assertEqual(
            detect_requested_structures("heart", "Show the right atrium and mitral valve"),
            ["right_atrium", "mitral_valve"],
        )
        self.assertEqual(
            detect_requested_structures("kidneys", "Focus on the renal artery"),
            ["renal_artery"],
        )

    def test_spec_rejects_unknown_structure(self) -> None:
        with self.assertRaises(ValueError):
            validate_anatomy_spec({"is_anatomy": True, "organ": "heart", "required_structures": ["invented_part"]})

    def test_default_view_references_real_structures(self) -> None:
        view = get_view("heart", "anterior_cutaway")
        known = {item["id"] for item in load_organ("heart")["structures"]["structures"]}
        self.assertTrue(set(view["required_structures"]).issubset(known))

    def test_spec_normalizes_new_contract_fields(self) -> None:
        spec = validate_anatomy_spec({
            "is_anatomy": True,
            "organ": "heart",
            "view": "front cutaway",
            "grade_level": "High School",
            "required_structures": ["Aorta", "left ventricle", "Aorta"],
            "focus_structures": ["left ventricle"],
            "detail_level": "advanced",
            "orientation": "Portrait",
            "show_flow": True,
        })
        self.assertEqual(spec["view"], "anterior_cutaway")
        self.assertEqual(spec["required_structures"], ["aorta", "left_ventricle"])
        self.assertEqual(spec["focus_structures"], ["left_ventricle"])
        self.assertEqual(spec["grade_level"], "high_school")
        self.assertEqual(spec["detail_level"], "advanced")
        self.assertEqual(spec["orientation"], "portrait")

    def test_custom_view_is_preserved_without_catalog_hardcoding(self) -> None:
        spec = validate_anatomy_spec({
            "is_anatomy": True,
            "organ": "heart",
            "view": "anterior_cutaway",
            "view_description": "posterior view from slightly above",
            "required_structures": ["aorta", "left_atrium"],
        })
        prompt = build_anatomy_prompt(spec)
        self.assertEqual(spec["view_description"], "posterior view from slightly above")
        self.assertIn("anatomical viewpoint or section: posterior view from slightly above", prompt)
        self.assertNotIn("Anterior cutaway:", prompt)

    def test_open_ended_view_wording_is_preserved(self) -> None:
        self.assertEqual(
            preserve_requested_view("posterior view of the heart for a biology student"),
            "posterior view of the heart for a biology student",
        )
        self.assertEqual(preserve_requested_view("top side of eye"), "top side of eye")
        self.assertEqual(preserve_requested_view("brain"), "")

    def test_runtime_view_extraction_is_concise(self) -> None:
        self.assertEqual(
            extract_requested_view("posterior view of the heart for a biology student"),
            "posterior view",
        )
        self.assertEqual(
            extract_requested_view("create an oblique posterior view from above of the pancreas"),
            "oblique posterior view from above",
        )
        self.assertEqual(extract_requested_view("cross section view of brain"), "cross section view")

    def test_focus_must_be_required(self) -> None:
        with self.assertRaisesRegex(AnatomyKnowledgeError, "focus_structures"):
            validate_anatomy_spec({
                "is_anatomy": True,
                "organ": "heart",
                "required_structures": ["aorta"],
                "focus_structures": ["left_ventricle"],
            })

    def test_grade_detail_compatibility_is_enforced(self) -> None:
        with self.assertRaisesRegex(AnatomyKnowledgeError, "incompatible"):
            validate_anatomy_spec({
                "is_anatomy": True,
                "organ": "brain",
                "grade_level": "primary_school",
                "detail_level": "advanced",
                "required_structures": ["cerebrum"],
            })

    def test_deterministic_builder_is_stable_and_label_free(self) -> None:
        source = {
            "is_anatomy": True,
            "organ": "heart",
            "required_structures": ["aorta", "left_ventricle"],
            "focus_structures": ["left_ventricle"],
            "grade_level": "middle_school",
            "detail_level": "intermediate",
            "orientation": "portrait",
            "show_flow": False,
        }
        first = build_anatomy_prompt(source)
        second = build_anatomy_prompt(source)
        self.assertEqual(first, second)
        for phrase in ("HRTANAT", "Aorta", "Left ventricle", "white or very light neutral background", "no labels", "no arrows", "no watermark"):
            self.assertIn(phrase, first)

    def test_compiler_validates_and_builds_at_one_trust_boundary(self) -> None:
        validated, prompt = compile_anatomy_prompt({
            "is_anatomy": True,
            "organ": "heart",
            "view": "front cutaway",
            "required_structures": ["Aorta", "left ventricle"],
            "focus_structures": ["left ventricle"],
        })
        self.assertEqual(validated["view"], "anterior_cutaway")
        self.assertEqual(validated["required_structures"], ["aorta", "left_ventricle"])
        self.assertIn("Aorta", prompt)
        self.assertIn("no labels", prompt)

    def test_unsupported_organ_uses_general_anatomy_compiler(self) -> None:
        validated, prompt = compile_general_anatomy_prompt({
            "is_anatomy": True,
            "catalog_verified": False,
            "organ": "pancreas",
            "view_description": "posterior cross-section",
            "required_structures": ["pancreatic duct"],
            "grade_level": "high_school",
        })
        self.assertFalse(validated["catalog_verified"])
        self.assertEqual(validated["organ"], "pancreas")
        self.assertIn("posterior cross-section", prompt)
        self.assertIn("white or very light neutral background", prompt)
        self.assertIn("no labels", prompt)
        self.assertIn("do not add unrelated organs", prompt)

    def test_bare_anatomy_subject_uses_concise_prompt(self) -> None:
        validated, prompt = compile_general_anatomy_prompt({
            "is_anatomy": True,
            "organ": "intestine",
            "_minimal_prompt": True,
        })
        self.assertEqual(validated["organ"], "intestine")
        self.assertEqual(validated["prompt_profile"], "minimal")
        self.assertIn("one isolated human intestine", prompt)
        self.assertIn("white or very light neutral background", prompt)
        self.assertIn("no labels", prompt)
        self.assertNotIn("general audience", prompt)
        self.assertNotIn("portrait composition", prompt)
        self.assertNotIn("laterality", prompt)
        revalidated, recompiled = compile_general_anatomy_prompt(validated)
        self.assertEqual(revalidated["prompt_profile"], "minimal")
        self.assertEqual(recompiled, prompt)

    def test_any_anatomy_compiler_selects_catalog_or_general_path(self) -> None:
        verified, _ = compile_any_anatomy_prompt({
            "is_anatomy": True,
            "organ": "heart",
            "required_structures": ["aorta"],
        })
        general, _ = compile_any_anatomy_prompt({
            "is_anatomy": True,
            "organ": "spleen",
            "required_structures": [],
        })
        self.assertNotIn("catalog_verified", verified)
        self.assertFalse(general["catalog_verified"])

    def test_all_organs_build_valid_prompts(self) -> None:
        for organ in list_supported_organs():
            knowledge = load_organ(organ)
            view = get_view(organ, knowledge["views"]["default_view"])
            prompt = build_anatomy_prompt({
                "is_anatomy": True,
                "organ": organ,
                "view": view["id"],
                "required_structures": view["required_structures"][:2],
            })
            self.assertIn(knowledge["structures"]["trigger_word"], prompt)

    def test_all_organs_build_catalog_driven_output_schemas(self) -> None:
        for organ in list_supported_organs():
            knowledge = load_organ(organ)
            schema = build_anatomy_extraction_schema(organ)
            spec = schema["properties"]["anatomy_spec"]
            properties = spec["properties"]
            self.assertEqual(properties["organ"]["enum"], [organ])
            self.assertEqual(
                set(properties["required_structures"]["items"]["enum"]),
                {item["id"] for item in knowledge["structures"]["structures"]},
            )
            self.assertEqual(
                set(properties["view"]["enum"]),
                {item["id"] for item in knowledge["views"]["views"]},
            )
            self.assertEqual(properties["required_structures"]["maxItems"], 8)


if __name__ == "__main__":
    unittest.main()
