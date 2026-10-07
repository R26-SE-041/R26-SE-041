"""
Extends manual_smoketest.py from 2 organs (heart, brain) to all 5 organs the
anatomy catalog currently supports (brain, heart, kidneys, liver, lungs),
comparing raw_base vs agentic_pipeline against the already-deployed Modal
agents. Existing valid records in manual_smoketest_results.json are reused
(not re-run) to avoid paying for GPU inference twice; only missing
(organ, condition) pairs are executed.

This is still a bounded, cheap, honest sample -- not the full pre-registered
100-prompt x 5-seed ablation. finetuned_pipeline is skipped because the
anatomy LoRA adapter is not currently installed (checked via prompt-agent
/health -> anatomy_lora_installed).

Run from koji-interactive-infographic-generator/backend:
    python evaluation/results/run_full_smoketest.py
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

BASE = "https://agal-koji--{}-api.modal.run"
PROMPT_URL = BASE.format("prompt-agent")
IMAGE_URL = BASE.format("image-agent")
EVAL_URL = BASE.format("eval-agent")

ORGANS = ["heart", "brain", "kidneys", "liver", "lungs"]
CONDITIONS = ("raw_base", "agentic_pipeline")
OUT_PATH = Path(__file__).parent / "manual_smoketest_results.json"
IMG_DIR = Path(__file__).parent / "images"
IMG_DIR.mkdir(exist_ok=True)


def post(url: str, payload: dict, timeout: int = 300) -> tuple[dict, float]:
    t0 = time.monotonic()
    resp = requests.post(url, json=payload, timeout=timeout)
    elapsed = time.monotonic() - t0
    resp.raise_for_status()
    return resp.json(), elapsed


def is_valid(record: dict) -> bool:
    return bool(record.get("eval_raw")) and not record.get("fatal_error") and not record.get("generate_error")


def run_condition(organ: str, condition: str) -> dict:
    print(f"\n=== {organ} / {condition} ===", flush=True)
    record: dict = {"organ": organ, "condition": condition}

    if condition == "raw_base":
        raw_prompt = organ
        enhanced_prompt = organ
        anatomy_spec = {"is_anatomy": False}
        img_resp, gen_latency = post(
            IMAGE_URL + "/generate",
            {
                "prompt": raw_prompt,
                "domain": "generic",
                "use_skill_rules": False,
                "speed_mode": "normal",
            },
        )
        enable_anatomy_critic = False
    else:  # agentic_pipeline
        raw_prompt = f"Show me the human {organ} anatomy for a biology student"
        enh_resp, enh_latency = post(
            PROMPT_URL + "/enhance",
            {
                "raw_prompt": raw_prompt,
                "speed_mode": "normal",
                "use_memento": False,
                "use_skill_rules": True,
            },
        )
        record["enhance_latency_s"] = round(enh_latency, 2)
        enhanced_prompt = enh_resp.get("final_prompt") or raw_prompt
        anatomy_spec = enh_resp.get("anatomy_spec") or {"is_anatomy": False}
        record["prompt_agent_raw_response_keys"] = list(enh_resp.keys())
        print(f"  enhanced_prompt: {enhanced_prompt[:200]}")
        print(f"  anatomy_spec: {anatomy_spec}")

        img_resp, gen_latency = post(
            IMAGE_URL + "/generate",
            {
                "prompt": enhanced_prompt,
                "domain": "anatomy" if anatomy_spec.get("is_anatomy") else "generic",
                "organ": anatomy_spec.get("organ") or organ,
                "use_skill_rules": True,
                "speed_mode": "normal",
            },
        )
        enable_anatomy_critic = bool(anatomy_spec.get("is_anatomy"))

    record["raw_prompt"] = raw_prompt
    record["enhanced_prompt"] = enhanced_prompt
    record["generate_latency_s"] = round(gen_latency, 2)
    record["generate_error"] = img_resp.get("error")

    image_b64 = img_resp.get("image_base64")
    if not image_b64:
        record["eval_skipped_reason"] = "no image returned"
        print(f"  NO IMAGE: {img_resp.get('error')}")
        return record

    img_path = IMG_DIR / f"{organ}_{condition}.png"
    img_path.write_bytes(base64.b64decode(image_b64))
    record["image_file"] = str(img_path.name)
    print(f"  image saved: {img_path} ({gen_latency:.1f}s)")

    eval_resp, eval_latency = post(
        EVAL_URL + "/evaluate",
        {
            "image_base64": image_b64,
            "raw_prompt": raw_prompt,
            "enhanced_prompt": enhanced_prompt,
            "anatomy_spec": anatomy_spec,
            "enable_anatomy_critic": enable_anatomy_critic,
        },
        timeout=300,
    )
    record["eval_latency_s"] = round(eval_latency, 2)
    record["eval_raw"] = eval_resp
    print(f"  eval: {json.dumps(eval_resp, indent=2)[:800]}")

    return record


def main() -> None:
    existing: list[dict] = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else []
    by_key = {(r.get("organ"), r.get("condition")): r for r in existing}

    results: list[dict] = []
    for organ in ORGANS:
        for condition in CONDITIONS:
            key = (organ, condition)
            prior = by_key.get(key)
            if prior and is_valid(prior):
                print(f"\n=== {organ} / {condition} === (reusing existing valid result)")
                results.append(prior)
                continue
            try:
                results.append(run_condition(organ, condition))
            except Exception as exc:  # noqa: BLE001
                print(f"  FAILED: {exc}")
                results.append({"organ": organ, "condition": condition, "fatal_error": str(exc)})
            OUT_PATH.write_text(json.dumps(results, indent=2))
    OUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
