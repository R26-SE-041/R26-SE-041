from __future__ import annotations

import unittest
import json
from pathlib import Path

from training.prompt.validate_dataset import validate
from training.prompt.evaluate_models import _score


class PromptTrainingDataTests(unittest.TestCase):
    def test_colab_notebook_python_cells_compile(self) -> None:
        notebook_dir = Path(__file__).resolve().parents[1] / "training" / "prompt"
        for name in ("EduVision_Qwen25_3B_Anatomy_QLoRA.ipynb", "EduVision_Prompt_Base_vs_LoRA.ipynb"):
            notebook = json.loads((notebook_dir / name).read_text(encoding="utf-8"))
            for index, cell in enumerate(notebook["cells"]):
                if cell["cell_type"] != "code":
                    continue
                source = "".join(cell["source"])
                python_only = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(("!", "%")))
                if python_only.strip():
                    compile(python_only, f"{name}:cell-{index}", "exec")

    def test_frozen_dataset_integrity(self) -> None:
        data_dir = Path(__file__).resolve().parents[1] / "training" / "prompt" / "data"
        result = validate(data_dir)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["train"]["total"], 3600)
        self.assertEqual(result["counts"]["validation"]["total"], 450)
        self.assertEqual(result["counts"]["test"]["total"], 450)

    def test_prompt_evaluation_metrics(self) -> None:
        expected = {
            "anatomy_spec": {
                "is_anatomy": True,
                "organ": "heart",
                "view": "anterior_cutaway",
                "grade_level": "middle_school",
                "required_structures": ["aorta", "right_atrium"],
                "focus_structures": ["right_atrium"],
                "detail_level": "intermediate",
                "orientation": "portrait",
                "show_flow": False,
            },
        }
        metrics, failures = _score(expected, expected, {"heart": {"aorta", "right_atrium"}})
        self.assertEqual(metrics["json_valid"], 1.0)
        self.assertEqual(metrics["composite_accuracy"], 1.0)
        self.assertEqual(failures, [])

    def test_invalid_json_is_hard_failure(self) -> None:
        metrics, failures = _score(None, {"anatomy_spec": {"is_anatomy": False}}, {}, None)
        self.assertEqual(metrics["json_valid"], 0.0)
        self.assertIn("invalid_json", failures)


if __name__ == "__main__":
    unittest.main()
