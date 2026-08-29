from __future__ import annotations

import unittest

from evaluation.anatomy.metrics import aggregate_runs, score_prompt, score_svg_layout


class AnatomyMetricTests(unittest.TestCase):
    def test_prompt_rules(self) -> None:
        scores = score_prompt(
            "Heart anterior cutaway, right atrium, no labels, no embedded text, light neutral background, empty side margins",
            {"organ": "heart", "view": "anterior_cutaway", "required_structures": ["right_atrium"]},
        )
        self.assertEqual(scores["organ_match"], 1.0)
        self.assertEqual(scores["clean_rule_coverage"], 1.0)

    def test_svg_recall(self) -> None:
        scores = score_svg_layout([
            {"structure_id": "heart.aorta", "anchor_x": 0.5, "anchor_y": 0.2, "label_x": 0.72, "label_y": 0.2, "confidence": 0.9, "verified": True},
        ], ["aorta", "right_atrium"])
        self.assertEqual(scores["canonical_id_recall"], 0.5)
        self.assertEqual(scores["verified_rate"], 1.0)

    def test_aggregate_is_variant_specific(self) -> None:
        summary = aggregate_runs([
            {"variant": "base", "latency_ms": 100, "metrics": {"score": 0.5}},
            {"variant": "improved", "latency_ms": 150, "metrics": {"score": 0.9}},
        ])
        self.assertEqual(summary["base"]["metrics"]["score"], 0.5)
        self.assertEqual(summary["improved"]["metrics"]["score"], 0.9)


if __name__ == "__main__":
    unittest.main()
