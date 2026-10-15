import unittest
from unittest.mock import Mock
from types import SimpleNamespace
from pydantic import ValidationError
from shared.sketch import DEFAULT_PROMPT, SketchRequest, generation_prompt, render_generation_control, render_sketch
from shared.sketch_generation import (
    SketchUnderstanding, SketchQuality, control_settings, generate_from_sketch, prompt_chunks, sketch_prompt,
)

class SketchTests(unittest.TestCase):
    def test_control_map_and_original_have_opposite_polarity(self):
        req = SketchRequest(strokes=[{"points": [[0.2, 0.5], [0.8, 0.5]], "width": 0.01}])
        original = render_sketch(req.strokes)
        control = render_sketch(req.strokes, control=True)
        self.assertEqual(original.getpixel((512, 512)), (0, 0, 0))
        self.assertEqual(control.getpixel((512, 512)), (255, 255, 255))
        self.assertEqual(control.getpixel((0, 0)), (0, 0, 0))

    def test_erased_sketch_rejected(self):
        req = SketchRequest(strokes=[{"points": [[0.5, 0.5]], "width": 0.01},
            {"points": [[0.5, 0.5]], "width": 0.08, "tool": "eraser"}])
        with self.assertRaisesRegex(ValueError, "blank"):
            render_sketch(req.strokes)

    def test_edge_to_edge_sketch_is_centered_with_safe_generation_margins(self):
        req = SketchRequest(strokes=[{"points": [[0, 0], [1, 1]], "width": .01}])
        control = render_generation_control(req.strokes)
        bounds = control.getbbox()
        self.assertGreaterEqual(bounds[0], 90)
        self.assertGreaterEqual(bounds[1], 90)
        self.assertLessEqual(bounds[2], 934)
        self.assertLessEqual(bounds[3], 934)

    def test_invalid_sketch_rejected(self):
        for strokes in ([], [{"points": [[-0.1, 0.5]]}],
            [{"points": [[float("nan"), 0.5]]}], [{"points": [[0.5, 0.5]], "tool": "eraser"}]):
            with self.subTest(strokes=strokes), self.assertRaises(ValidationError):
                SketchRequest(strokes=strokes)

    def test_prompt_is_optional_and_user_instruction_is_preserved(self):
        self.assertEqual(generation_prompt("  "), DEFAULT_PROMPT)
        self.assertTrue(generation_prompt("  cartoon fish  ").startswith("cartoon fish"))
        self.assertIn("plain white background", generation_prompt("cartoon fish"))

    def test_complexity_limit(self):
        with self.assertRaisesRegex(ValidationError, "complex"):
            SketchRequest(strokes=[{"points": [[0.5, 0.5]] * 5000}] * 7)


class SketchGenerationTests(unittest.TestCase):
    def setUp(self):
        self.req = SketchRequest(strokes=[{"points": [[.2, .5], [.8, .5]]}], seed=42)
        self.subject = {"subject": "fish", "confidence": .95, "is_anatomy": False,
                        "organ": "", "view": "external side view", "description": "Orange scales and blue fins",
                        "visible_structures": [], "clarification": ""}
        self.quality = dict(subject_matches=True, finished_color=True, white_background=True,
                            complete_subject=True, clean_image=True, anatomy_correct=None, score=8.0, feedback="Clear")
        self.render = Mock(side_effect=lambda prompt, seed, settings: {
            "image_base64": f"image-{seed}", "generation_metadata": {"seed": seed, **settings}})

    def run_pipeline(self, subject=None, checks=None):
        return generate_from_sketch(self.req, Mock(return_value=subject or self.subject), self.render,
                                    Mock(side_effect=checks or [self.quality]))

    def test_generic_drawing_has_color_white_background_and_verified_metadata(self):
        result = self.run_pipeline()
        self.assertEqual(result["anatomy_spec"], {"is_anatomy": False})
        self.assertIn("Full-color", result["prompt"])
        self.assertIn("plain white background", result["prompt"])
        self.assertIn("margins", result["prompt"])
        self.assertEqual(result["generation_metadata"]["quality_status"], "passed")
        self.assertEqual(result["generation_metadata"]["requested_control_strength"], .85)
        self.assertEqual(result["image_base64"], "image-42")
        self.render.assert_called_once()

    def test_ambiguous_drawing_does_not_allocate_renderer(self):
        result = self.run_pipeline({**self.subject, "confidence": .4, "clarification": "Eye or leaf?"})
        self.assertEqual(result["error_code"], "clarification_required")
        self.assertIn("Additional instruction", result["error"])
        self.render.assert_not_called()

    def test_exterior_eye_does_not_force_internal_cutaway(self):
        subject = {**self.subject, "is_anatomy": True, "organ": "eye", "subject": "human eye",
                   "view": "anterior external view", "description": "Brown iris, black pupil, white sclera",
                   "visible_structures": ["iris", "pupil", "sclera"]}
        result = self.run_pipeline(subject, [{**self.quality, "anatomy_correct": True}])
        self.assertTrue(result["anatomy_spec"]["is_anatomy"])
        self.assertFalse(result["anatomy_spec"]["catalog_verified"])
        self.assertEqual(result["anatomy_spec"]["required_structures"], ["iris", "pupil", "sclera"])
        self.assertNotIn("retina", result["prompt"])
        self.assertNotIn("cross-sectional cutaway", result["prompt"])
        self.assertIn("natural tissue colors", result["prompt"])

    def test_catalog_organ_visible_structures_keep_canonical_ids(self):
        subject = SketchUnderstanding(**{**self.subject, "is_anatomy": True, "organ": "heart",
            "subject": "human heart", "view": "anterior external view", "visible_structures": ["aorta"]})
        _, anatomy = sketch_prompt(subject, "")
        self.assertEqual(anatomy["organ"], "heart")
        self.assertEqual(anatomy["required_structures"], ["aorta"])

    def test_uncatalogued_hand_is_supported_without_forcing_internal_parts(self):
        subject = SketchUnderstanding(**{**self.subject, "is_anatomy": True, "organ": "hand",
            "subject": "human hand", "view": "palm external view", "visible_structures": ["thumb", "fingers"]})
        prompt, anatomy = sketch_prompt(subject, "")
        self.assertEqual(anatomy["organ"], "hand")
        self.assertNotIn("cutaway", prompt)

    def test_failed_color_check_retries_once_and_retains_original_requested_strength(self):
        result = self.run_pipeline(checks=[{**self.quality, "finished_color": False}, self.quality])
        self.assertEqual(self.render.call_count, 2)
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["image_base64"], "image-43")
        self.assertIn("Replace sketch lines", self.render.call_args.args[0])
        self.assertLess(self.render.call_args.args[2]["control_strength"], .85)
        self.assertEqual(result["generation_metadata"]["requested_control_strength"], .85)
        self.assertIsNone(result["quality_warning"])

    def test_two_failed_checks_return_best_with_notice_and_no_more_retries(self):
        result = self.run_pipeline(checks=[{**self.quality, "finished_color": False},
            {**self.quality, "finished_color": False, "white_background": False, "score": 10.0}])
        self.assertEqual(self.render.call_count, 2)
        self.assertEqual(result["image_base64"], "image-42")
        self.assertEqual(result["generation_metadata"]["quality_status"], "needs_review")
        self.assertIn("sketch lines", result["quality_warning"])

    def test_inspection_failure_preserves_image_but_does_not_claim_verified(self):
        result = self.run_pipeline(checks=[RuntimeError("vision unavailable")])
        self.assertEqual(result["image_base64"], "image-42")
        self.assertEqual(result["generation_metadata"]["quality_status"], "unverified")
        self.assertIn("unverified", result["quality_warning"])

    def test_retry_gpu_failure_preserves_first_image(self):
        self.render.side_effect = [{"image_base64": "first", "generation_metadata": {"seed": 42}},
                                   RuntimeError("GPU unavailable")]
        result = self.run_pipeline(checks=[{**self.quality, "finished_color": False}])
        self.assertEqual(result["image_base64"], "first")
        self.assertIn("retry unavailable", result["quality_warning"])

    def test_false_string_cannot_pass_quality_gate(self):
        with self.assertRaises(ValidationError):
            SketchQuality(**{**self.quality, "finished_color": "false"})

    def test_anatomy_cannot_pass_without_positive_structure_check(self):
        self.assertTrue(SketchQuality(**self.quality).failures(True))
        for strength in (.5, .85, 1.2):
            self.assertLessEqual(control_settings(strength, True)["control_strength"], .85)
            self.assertLess(control_settings(strength, False)["control_guidance_end"], 1)

    def test_prompt_chunks_preserve_details_and_fit_both_encoders(self):
        tokenizers = [SimpleNamespace(model_max_length=8, encode=lambda text: text.split() + [0, 0]),
                      SimpleNamespace(model_max_length=7, encode=lambda text: text.split() + [0, 0])]
        prompt = "coloured human eye plain white background brown iris black pupil"
        chunks = prompt_chunks(prompt, tokenizers)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks), prompt)
        for chunk in chunks:
            self.assertTrue(all(len(t.encode(chunk)) <= t.model_max_length for t in tokenizers))
