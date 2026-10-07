import unittest
from pydantic import ValidationError
from shared.sketch import DEFAULT_PROMPT, SketchRequest, generation_prompt, render_sketch

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

    def test_invalid_sketch_rejected(self):
        for strokes in ([], [{"points": [[-0.1, 0.5]]}],
            [{"points": [[float("nan"), 0.5]]}], [{"points": [[0.5, 0.5]], "tool": "eraser"}]):
            with self.subTest(strokes=strokes), self.assertRaises(ValidationError):
                SketchRequest(strokes=strokes)

    def test_prompt_is_optional_and_user_instruction_is_preserved(self):
        self.assertEqual(generation_prompt("  "), DEFAULT_PROMPT)
        self.assertEqual(generation_prompt("  cartoon fish  "), "cartoon fish")

    def test_complexity_limit(self):
        with self.assertRaisesRegex(ValidationError, "complex"):
            SketchRequest(strokes=[{"points": [[0.5, 0.5]] * 5000}] * 7)
