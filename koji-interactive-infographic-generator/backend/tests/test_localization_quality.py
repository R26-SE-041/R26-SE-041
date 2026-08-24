from __future__ import annotations

import unittest

from anatomy.localization_quality import filter_localizations


def annotation(structure_id: str, x: float, y: float, confidence: float, bbox: list[float]) -> dict:
    return {
        "structure_id": structure_id,
        "label": structure_id,
        "anchor_x": x,
        "anchor_y": y,
        "bbox": bbox,
        "confidence": confidence,
    }


class LocalizationQualityTests(unittest.TestCase):
    def test_rejects_low_confidence_localization(self) -> None:
        result = filter_localizations([
            annotation("heart.aorta", 0.5, 0.2, 0.81, [0.45, 0.1, 0.6, 0.3]),
        ])
        self.assertEqual(result, [])

    def test_keeps_strongest_of_colliding_structures(self) -> None:
        result = filter_localizations([
            annotation("heart.pulmonary_valve", 0.40, 0.25, 0.84, [0.36, 0.2, 0.46, 0.3]),
            annotation("heart.mitral_valve", 0.41, 0.26, 0.93, [0.37, 0.21, 0.47, 0.31]),
        ])
        self.assertEqual([item["structure_id"] for item in result], ["heart.mitral_valve"])
        self.assertTrue(result[0]["verified"])

    def test_preserves_distinct_verified_structures(self) -> None:
        result = filter_localizations([
            annotation("heart.aorta", 0.55, 0.18, 0.91, [0.48, 0.08, 0.62, 0.28]),
            annotation("heart.right_ventricle", 0.44, 0.66, 0.88, [0.31, 0.48, 0.51, 0.82]),
        ])
        self.assertEqual(len(result), 2)
        self.assertTrue(all(item["verified"] for item in result))

    # ── New: bbox area gates ─────────────────────────────────────────────────

    def test_rejects_trivially_small_bbox(self) -> None:
        """A bbox that covers < 0.15% of image area is noise/guessing."""
        result = filter_localizations([
            annotation("heart.aorta", 0.5, 0.5, 0.95, [0.499, 0.499, 0.501, 0.501]),
        ])
        self.assertEqual(result, [])

    def test_rejects_huge_bbox_covering_whole_image(self) -> None:
        """A bbox covering > 65% of the image is not a specific structure."""
        result = filter_localizations([
            annotation("heart.aorta", 0.5, 0.5, 0.95, [0.05, 0.05, 0.95, 0.95]),
        ])
        self.assertEqual(result, [])

    # ── New: edge-proximity anchor rejection ─────────────────────────────────

    def test_rejects_anchor_near_image_edge(self) -> None:
        """Anchors within 2% of any edge are almost always background."""
        # Anchor at x=0.01 (left edge)
        result = filter_localizations([
            annotation("heart.aorta", 0.01, 0.5, 0.95, [0.03, 0.4, 0.15, 0.6]),
        ])
        self.assertEqual(result, [])
        # Anchor at y=0.99 (bottom edge)
        result = filter_localizations([
            annotation("heart.aorta", 0.5, 0.99, 0.95, [0.4, 0.85, 0.6, 0.97]),
        ])
        self.assertEqual(result, [])

    # ── New: duplicate structure IDs ─────────────────────────────────────────

    def test_rejects_duplicate_structure_ids(self) -> None:
        """Only the highest-confidence proposal for a given structure_id should be kept."""
        result = filter_localizations([
            annotation("heart.aorta", 0.3, 0.3, 0.88, [0.25, 0.2, 0.35, 0.4]),
            annotation("heart.aorta", 0.6, 0.6, 0.92, [0.55, 0.5, 0.65, 0.7]),
        ])
        self.assertEqual(len(result), 1)
        # The higher-confidence one should win
        self.assertAlmostEqual(result[0]["anchor_x"], 0.6)

    # ── New: verified flag ───────────────────────────────────────────────────

    def test_verified_flag_only_on_accepted_items(self) -> None:
        """Items that pass all gates should have verified=True.
        Items that don't pass should not appear in the output at all."""
        result = filter_localizations([
            annotation("heart.aorta", 0.5, 0.5, 0.90, [0.4, 0.35, 0.6, 0.65]),
        ])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["verified"])

    def test_mask_anchor_not_empty_space_centroid(self) -> None:
        """A reasonable bbox with a valid anchor should pass.
        This test verifies the filter doesn't reject legitimate proposals."""
        result = filter_localizations([
            annotation("heart.left_ventricle", 0.45, 0.65, 0.89, [0.35, 0.50, 0.55, 0.80]),
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["structure_id"], "heart.left_ventricle")
        self.assertTrue(result[0]["verified"])

    # ── New: invisible structures (all filtered) ─────────────────────────────

    def test_all_invisible_structures_produce_empty_result(self) -> None:
        """When all proposals fail quality gates, result is empty.
        This represents 'no label' being preferred over wrong labels."""
        result = filter_localizations([
            annotation("heart.mitral_valve", 0.5, 0.5, 0.75, [0.4, 0.4, 0.6, 0.6]),   # low confidence
            annotation("heart.tricuspid_valve", 0.01, 0.5, 0.90, [0.03, 0.4, 0.1, 0.6]),  # edge anchor
            annotation("heart.aortic_valve", 0.5, 0.5, 0.95, [0.49, 0.49, 0.51, 0.51]),  # tiny bbox
        ])
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
