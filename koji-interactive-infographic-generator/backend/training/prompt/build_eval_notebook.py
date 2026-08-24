"""Build the paired base-versus-LoRA Colab evaluation notebook."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def cell(kind: str, source: str) -> dict:
    payload = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
    if kind == "code":
        payload.update({"execution_count": None, "outputs": []})
    return payload


def build() -> Path:
    cells = [
        cell("markdown", """# EduVision prompt agent: base vs Anatomy LoRA

Runs paired deterministic inference on the frozen 450-example test split. It reports JSON validity, routing, organ/view accuracy, canonical required/focus structure precision and recall, grade/detail/orientation accuracy, strict output-contract compliance, flow accuracy, hard failures, mean/p50/p95 latency, per-organ results, and a paired bootstrap 95% interval.

Run the 60-example balanced pilot first. If it succeeds, run the full test cell."""),
        cell("code", """!pip -q install "transformers==4.51.3" "peft==0.15.2" "accelerate==1.6.0" "bitsandbytes==0.45.5" "sentencepiece>=0.2.0"""),
        cell("code", """import hashlib, json, shutil, zipfile
from pathlib import Path
import torch
from google.colab import files

assert torch.cuda.is_available(), "Select a GPU runtime"
uploaded = files.upload()
expected = {"test.jsonl", "manifest.json", "prompt-anatomy-lora.zip", "evaluate_models.py"}
missing = expected - set(uploaded)
assert not missing, f"Missing files: {sorted(missing)}"
WORK = Path("/content/prompt_eval")
WORK.mkdir(exist_ok=True)
for name in expected:
    (WORK / name).write_bytes(uploaded[name])
manifest = json.loads((WORK / "manifest.json").read_text())
actual = hashlib.sha256((WORK / "test.jsonl").read_bytes()).hexdigest()
assert actual == manifest["sha256"]["test.jsonl"], "Frozen test hash mismatch"
with zipfile.ZipFile(WORK / "prompt-anatomy-lora.zip") as archive:
    archive.extractall(WORK / "adapter")
adapter_candidates = list((WORK / "adapter").rglob("adapter_config.json"))
assert len(adapter_candidates) == 1, adapter_candidates
ADAPTER_DIR = adapter_candidates[0].parent
print("GPU:", torch.cuda.get_device_name(0))
print("Adapter:", ADAPTER_DIR)
print("Frozen test verified:", actual)"""),
        cell("markdown", "## Balanced 60-example pilot"),
        cell("code", """!python /content/prompt_eval/evaluate_models.py \
  --test-file /content/prompt_eval/test.jsonl \
  --adapter "$ADAPTER_DIR" \
  --output-dir /content/prompt_eval/pilot_results \
  --limit 60"""),
        cell("markdown", "## Full 450-example conference evaluation\n\nRun only after inspecting the pilot. This can take a substantial amount of GPU time because it performs 900 deterministic generations."),
        cell("code", """!python /content/prompt_eval/evaluate_models.py \
  --test-file /content/prompt_eval/test.jsonl \
  --adapter "$ADAPTER_DIR" \
  --output-dir /content/prompt_eval/full_results"""),
        cell("code", """archive = shutil.make_archive("/content/prompt-base-vs-lora-results", "zip", "/content/prompt_eval/full_results")
files.download(archive)"""),
    ]
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "colab": {"name": "EduVision_Prompt_Base_vs_LoRA.ipynb", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
            "accelerator": "GPU",
        },
        "cells": cells,
    }
    output = HERE / "EduVision_Prompt_Base_vs_LoRA.ipynb"
    output.write_text(json.dumps(notebook, indent=1), encoding="utf-8", newline="\n")
    return output


if __name__ == "__main__":
    print(build())
