from __future__ import annotations

import unittest

from anatomy.grid_localization import inner_grid_points, keep_unique_masks


class GridLocalizationTests(unittest.TestCase):
    def test_six_by_six_grid_returns_only_inner_sixteen_centres(self) -> None:
        points = inner_grid_points()
        self.assertEqual(len(points), 16)
        self.assertEqual(points[0]["grid_index"], 0)
        self.assertAlmostEqual(points[0]["x"], 0.25)
        self.assertAlmostEqual(points[0]["y"], 0.25)
        self.assertAlmostEqual(points[-1]["x"], 0.75)
        self.assertAlmostEqual(points[-1]["y"], 0.75)
        self.assertTrue(all(1 <= point["grid_row"] <= 4 for point in points))
        self.assertTrue(all(1 <= point["grid_column"] <= 4 for point in points))

    def test_duplicate_and_extreme_masks_are_removed(self) -> None:
        masks = keep_unique_masks([
            {"bbox": [0.2, 0.2, 0.4, 0.4], "grid_index": 0},
            {"bbox": [0.205, 0.205, 0.405, 0.405], "grid_index": 1},
            {"bbox": [0.6, 0.6, 0.75, 0.75], "grid_index": 2},
            {"bbox": [0.0, 0.0, 1.0, 1.0], "grid_index": 3},
        ])
        self.assertEqual([item["grid_index"] for item in masks], [0, 2])


if __name__ == "__main__":
    unittest.main()
