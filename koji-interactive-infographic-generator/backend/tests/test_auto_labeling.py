from __future__ import annotations

import io
import unittest
from PIL import Image

from anatomy.auto_labeling import build_auto_label_assets, build_regions, validate_auto_labels


def sample_image_bytes() -> bytes:
    image = Image.new("RGB", (400, 400), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class AutoLabelingTests(unittest.TestCase):
    def test_regions_are_the_inner_sixteen_cells_of_a_six_by_six_grid(self) -> None:
        regions = build_regions((400, 400))
        self.assertEqual(len(regions), 16)
        self.assertEqual(regions[0]["bbox_px"], (67, 67, 133, 133))
        self.assertEqual(regions[1]["bbox_px"], (133, 67, 200, 133))
        self.assertEqual(regions[-1]["bbox_px"], (267, 267, 333, 333))
        self.assertEqual(regions[0]["anchor_px"], (100, 100))
        self.assertEqual(regions[0]["context_bbox_px"], (16, 16, 184, 184))
        self.assertEqual(regions[5]["anchor_px"], (166, 166))
        self.assertEqual(regions[5]["context_bbox_px"], (82, 82, 250, 250))

    def test_assets_contain_full_image_and_sixteen_marked_context_crops(self) -> None:
        assets = build_auto_label_assets(sample_image_bytes())
        self.assertGreater(len(assets["original_bytes"]), 100)
        self.assertEqual(len(assets["crop_bytes"]), 16)
        self.assertTrue(all(len(value) > 100 for value in assets["crop_bytes"]))
        first_crop = Image.open(io.BytesIO(assets["crop_bytes"][0])).convert("RGB")
        # The center pixel stays visible; the cyan ring is drawn around it.
        self.assertEqual(first_crop.getpixel((84, 84)), (255, 255, 255))
        self.assertGreater(first_crop.getpixel((92, 84))[2], first_crop.getpixel((92, 84))[0])

    def test_validation_uses_crop_center_and_removes_duplicates(self) -> None:
        regions = build_regions((400, 400))
        payload = {"regions": [
            {"region_id": "R1", "label": "Ascending colon", "confidence": 0.91, "visible": True},
            {"region_id": "R2", "label": "Ascending colon", "confidence": 0.82, "visible": True},
            {"region_id": "R3", "label": "unknown region", "confidence": 0.99, "visible": True},
            {"region_id": "R4", "label": "Transverse colon", "confidence": 0.50, "visible": True},
            {"region_id": "R5", "label": "colon", "confidence": 0.95, "visible": True},
        ]}
        annotations, diagnostics = validate_auto_labels(payload, regions, (400, 400))
        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0]["label"], "Ascending colon")
        self.assertEqual(annotations[0]["anchor_x"], 0.25)
        self.assertEqual(annotations[0]["anchor_y"], 0.25)
        self.assertEqual(annotations[0]["grounding"], "marker_grounded_context_crop_qwen_vl")
        self.assertEqual(diagnostics["rejected_duplicate"], 2)
        self.assertEqual(diagnostics["rejected_low_confidence"], 1)

    def test_missing_or_invalid_labels_create_no_pointer(self) -> None:
        regions = build_regions((400, 400))
        payload = {"regions": [
            {"region_id": "R1", "label": "", "confidence": 0.99, "visible": True},
            {"region_id": "R99", "label": "Colon", "confidence": 0.99, "visible": True},
            {"region_id": "R2", "label": "Colon", "confidence": 0.70, "visible": True},
        ]}
        annotations, diagnostics = validate_auto_labels(payload, regions, (400, 400))
        self.assertEqual(annotations, [])
        self.assertEqual(diagnostics["accepted_labels"], 0)


if __name__ == "__main__":
    unittest.main()
