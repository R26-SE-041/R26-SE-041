"""
Adds the missing third leg of the comparison: automatic structure NAME LABELING
via Qwen2.5-VL (the interactive-agent's /auto-labels endpoint, which is the
currently-supported implementation -- /localize-structures is deprecated and
returns nothing).

Runs /auto-labels against the images already generated and saved by
run_full_smoketest.py (no re-generation, so this only costs the labeling VLM
calls) for BOTH raw_base and agentic_pipeline, for all 5 organs. This lets the
paper report whether Qwen-VL can name real anatomical structures on the raw
FLUX.1-dev output at all, versus on our pipeline's clean, structured output.

The interactive-agent always loads its SKILL.md/PERSONA.md/MEMENTO.md via
MemoryManager at container start (agents/interactive-agent/modal_app.py,
_VLMAgentBase.load_model) -- there is no request-level flag to disable this,
so every /auto-labels call below already runs with the deployed system prompt
and skill rules active, matching production behavior exactly.

Run from koji-interactive-infographic-generator/backend:
    python evaluation/results/run_auto_labels.py
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

INTERACTIVE_URL = "https://agal-koji--interactive-agent-api.modal.run"
IMG_DIR = Path(__file__).parent / "images"
OUT_PATH = Path(__file__).parent / "auto_labels_results.json"

ORGANS = ["heart", "brain", "kidneys", "liver", "lungs"]
CONDITIONS = ("raw_base", "agentic_pipeline")

# Matches the anatomy_spec.view returned by prompt-agent for each organ in the
# already-completed agentic_pipeline runs (manual_smoketest_results.json).
VIEWS = {
    "heart": "anterior_cutaway",
    "brain": "",
    "kidneys": "paired_coronal_cutaway",
    "liver": "",
    "lungs": "",
}


def post(url: str, payload: dict, timeout: int = 300) -> tuple[dict, float]:
    t0 = time.monotonic()
    resp = requests.post(url, json=payload, timeout=timeout)
    elapsed = time.monotonic() - t0
    resp.raise_for_status()
    return resp.json(), elapsed


def main() -> None:
    results = []
    for organ in ORGANS:
        for condition in CONDITIONS:
            img_path = IMG_DIR / f"{organ}_{condition}.png"
            if not img_path.exists():
                print(f"SKIP {organ}/{condition}: {img_path} not found")
                continue
            print(f"\n=== {organ} / {condition} (/auto-labels) ===", flush=True)
            image_b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
            try:
                resp, latency = post(
                    f"{INTERACTIVE_URL}/auto-labels",
                    {
                        "image_base64": image_b64,
                        "domain": "anatomy",
                        "organ": organ,
                        "view": VIEWS.get(organ, ""),
                        "speed_mode": "pro",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  FAILED: {exc}")
                results.append({"organ": organ, "condition": condition, "fatal_error": str(exc)})
                OUT_PATH.write_text(json.dumps(results, indent=2))
                continue

            annotations = resp.get("annotations") or []
            diagnostics = resp.get("diagnostics") or {}
            labels = [f"{a.get('label')} ({a.get('confidence'):.2f})" for a in annotations]
            print(f"  latency: {latency:.1f}s  accepted: {diagnostics.get('accepted_labels')}  labels: {labels}")
            results.append({
                "organ": organ,
                "condition": condition,
                "latency_s": round(latency, 2),
                "diagnostics": diagnostics,
                "labels": [{"label": a.get("label"), "confidence": a.get("confidence")} for a in annotations],
                "error": resp.get("error"),
            })
            OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
