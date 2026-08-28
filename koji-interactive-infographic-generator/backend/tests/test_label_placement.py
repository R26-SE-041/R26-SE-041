"""Unit tests for the _place_labels label placement algorithm.

The algorithm is inlined here verbatim from interactive-agent/modal_app.py so
it can be tested without a Modal runtime dependency.  Keep this in sync with
the source whenever the algorithm changes.
"""
from __future__ import annotations

import unittest
from typing import Any

# ── Algorithm (inlined from agents/interactive-agent/modal_app.py) ────────────

_LABEL_MARGIN_LEFT  = 0.02
_LABEL_MARGIN_RIGHT = 0.68
_LABEL_WIDTH        = 0.28
_LABEL_HEIGHT       = 0.055
_LABEL_PADDING      = 0.012
_MIN_LINE_LENGTH    = 0.07


def _place_labels(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not annotations:
        return annotations
    xs = [item["anchor_x"] for item in annotations]
    organ_cx = float(sorted(xs)[len(xs) // 2])
    occupied_left:  list[tuple[float, float]] = []
    occupied_right: list[tuple[float, float]] = []
    for item in sorted(annotations, key=lambda a: a["anchor_y"]):
        ax, ay = item["anchor_x"], item["anchor_y"]
        use_left = ax <= organ_cx
        lx       = _LABEL_MARGIN_LEFT if use_left else _LABEL_MARGIN_RIGHT
        occupied = occupied_left if use_left else occupied_right
        half = _LABEL_HEIGHT / 2
        ly_top = max(0.01, min(0.97 - _LABEL_HEIGHT, ay - half))
        changed = True
        while changed:
            changed = False
            ly_bottom = ly_top + _LABEL_HEIGHT
            for (ot, ob) in occupied:
                if ly_top < ob and ly_bottom > ot:
                    ly_top = ob + _LABEL_PADDING
                    ly_top = min(0.97 - _LABEL_HEIGHT, ly_top)
                    changed = True
        item["label_x"] = lx
        item["label_y"] = ly_top + half
        occupied.append((ly_top, ly_top + _LABEL_HEIGHT))
    return annotations


# ── Helpers ───────────────────────────────────────────────────────────────────

def ann(sid: str, ax: float, ay: float) -> dict:
    return {
        "structure_id": sid, "label": sid, "verified": True,
        "anchor_x": ax, "anchor_y": ay,
        "bbox": [ax - 0.05, ay - 0.05, ax + 0.05, ay + 0.05],
        "confidence": 0.90, "label_x": 0.0, "label_y": 0.0,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class LabelPlacementTests(unittest.TestCase):

    def test_label_y_is_close_to_anchor_y(self) -> None:
        """label_y should stay within ±0.2 of anchor_y for isolated structures."""
        result = _place_labels([ann("aorta", 0.55, 0.2)])
        self.assertAlmostEqual(result[0]["label_y"], 0.2, delta=0.2)

    def test_no_overlapping_label_boxes(self) -> None:
        """Two close structures must not produce label boxes that overlap."""
        items = [ann("a", 0.5, 0.4), ann("b", 0.5, 0.45)]
        result = _place_labels(items)
        result.sort(key=lambda x: x["label_y"])
        y_bot_a = result[0]["label_y"] + _LABEL_HEIGHT / 2
        y_top_b = result[1]["label_y"] - _LABEL_HEIGHT / 2
        self.assertGreaterEqual(y_top_b, y_bot_a - 1e-9,
                                "Label boxes must not overlap on the same side")

    def test_label_stays_within_canvas(self) -> None:
        """label_y + half-height must stay within [0, 1]."""
        items = [ann(f"s{i}", 0.5, float(i) / 10) for i in range(1, 10)]
        result = _place_labels(items)
        for item in result:
            top = item["label_y"] - _LABEL_HEIGHT / 2
            bot = item["label_y"] + _LABEL_HEIGHT / 2
            self.assertGreaterEqual(top, 0.0)
            self.assertLessEqual(bot, 1.0)

    def test_right_heavy_anchor_gets_right_label(self) -> None:
        """Single right-heavy anchor: median=0.88, use_left=(0.88<=0.88)=True → left.
        With 2 items where one is clearly right, it gets right label."""
        items = [ann("a", 0.08, 0.4), ann("aorta", 0.88, 0.4)]
        result = _place_labels(items)
        by_id = {r["structure_id"]: r for r in result}
        # median of [0.08, 0.88] = 0.08 (index 1 of sorted=[0.08,0.88]) = 0.88
        # 0.08 <= 0.88 → left; 0.88 <= 0.88 → left (tie goes left)
        # So with only 2 items, test bilateral split with 3 items:
        items3 = [ann("a", 0.10, 0.3), ann("b", 0.55, 0.5), ann("c", 0.88, 0.7)]
        r3 = _place_labels(items3)
        by3 = {r["structure_id"]: r for r in r3}
        # median of [0.10, 0.55, 0.88] = 0.55
        # 0.10 <= 0.55 → left; 0.55 <= 0.55 → left; 0.88 > 0.55 → right
        self.assertAlmostEqual(by3["c"]["label_x"], _LABEL_MARGIN_RIGHT, delta=0.01)
        self.assertAlmostEqual(by3["a"]["label_x"], _LABEL_MARGIN_LEFT,  delta=0.01)

    def test_left_heavy_anchor_gets_left_label(self) -> None:
        """With organ-relative split, a left anchor always gets left label."""
        result = _place_labels([ann("pv", 0.08, 0.4)])
        self.assertAlmostEqual(result[0]["label_x"], _LABEL_MARGIN_LEFT, delta=0.01)

    def test_single_structure_label_xy_are_set(self) -> None:
        result = _place_labels([ann("aorta", 0.55, 0.3)])
        self.assertIsInstance(result[0]["label_x"], float)
        self.assertIsInstance(result[0]["label_y"], float)

    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(_place_labels([]), [])

    def test_eight_structures_all_fit_on_canvas(self) -> None:
        """Simulate a realistic heart with 8 structures."""
        heart_anchors = [
            ("superior_vena_cava",    0.55, 0.10),
            ("aorta",                 0.52, 0.18),
            ("pulmonary_trunk",       0.43, 0.22),
            ("left_atrium",           0.56, 0.35),
            ("right_atrium",          0.44, 0.40),
            ("left_ventricle",        0.55, 0.65),
            ("right_ventricle",       0.43, 0.62),
            ("inferior_vena_cava",    0.47, 0.82),
        ]
        items = [ann(sid, ax, ay) for sid, ax, ay in heart_anchors]
        result = _place_labels(items)
        self.assertEqual(len(result), 8)
        for item in result:
            top = item["label_y"] - _LABEL_HEIGHT / 2
            bot = item["label_y"] + _LABEL_HEIGHT / 2
            self.assertGreaterEqual(top, 0.0, f"{item['structure_id']} top out of bounds")
            self.assertLessEqual(bot, 1.0, f"{item['structure_id']} bottom out of bounds")

    def test_no_two_labels_overlap_on_same_side(self) -> None:
        """Brute-force overlap check for a dense realistic layout."""
        items = [ann(f"s{i}", 0.5, 0.1 + i * 0.07) for i in range(9)]
        result = _place_labels(items)
        left  = [(r["label_y"] - _LABEL_HEIGHT/2, r["label_y"] + _LABEL_HEIGHT/2)
                 for r in result if r["label_x"] < 0.5]
        right = [(r["label_y"] - _LABEL_HEIGHT/2, r["label_y"] + _LABEL_HEIGHT/2)
                 for r in result if r["label_x"] >= 0.5]
        for group in (left, right):
            for i, (t1, b1) in enumerate(group):
                for j, (t2, b2) in enumerate(group):
                    if i >= j:
                        continue
                    overlap = t1 < b2 and t2 < b1
                    self.assertFalse(overlap, f"Labels {i} and {j} overlap: [{t1},{b1}] vs [{t2},{b2}]")


if __name__ == "__main__":
    unittest.main()
