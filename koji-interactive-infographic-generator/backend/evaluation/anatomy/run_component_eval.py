"""Run paired base/pipeline endpoint evaluation with fixed prompts and seeds.

This script uses only the Python standard library. It deliberately does not train,
promote memories, or mutate production data.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from anatomy import get_view
from evaluation.anatomy.metrics import aggregate_runs, score_prompt, score_svg_layout


HERE = Path(__file__).resolve().parent


def post_json(url: str, payload: dict[str, Any], timeout: int = 900) -> tuple[dict[str, Any], float]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {detail}") from exc
    return result, (time.perf_counter() - started) * 1000


def run_case(
    prompt_url: str,
    image_url: str,
    interactive_url: str,
    eval_url: str,
    raw_prompt: str,
    seed: int,
    variant: str,
) -> dict[str, Any]:
    use_pipeline = variant != "raw_base"
    use_lora = variant == "finetuned_pipeline"
    prompt_ms = 0.0
    enhanced: dict[str, Any] = {}
    if use_pipeline:
        enhanced, prompt_ms = post_json(f"{prompt_url.rstrip('/')}/enhance", {
            "raw_prompt": raw_prompt,
            "seed": seed,
            "speed_mode": "pro",
            "model_variant": "heart_lora" if use_lora else "base",
            "use_skill_rules": True,
            "use_memento": True,
        })
    final_prompt = str(enhanced.get("enhanced_prompt") or raw_prompt)
    anatomy_spec = enhanced.get("anatomy_spec") or {"is_anatomy": True, "organ": "heart", "view": "anterior_cutaway"}
    image, image_ms = post_json(f"{image_url.rstrip('/')}/generate", {
        "prompt": final_prompt,
        "seed": seed,
        "speed_mode": "pro",
        "model_variant": "heart_lora" if use_lora else "base",
        "domain": "anatomy" if use_pipeline else "generic",
        "organ": "heart",
        "view": "anterior_cutaway",
        "use_skill_rules": use_pipeline,
    })
    image_base64 = image.get("base_image_base64") or image.get("image_base64")
    if not image_base64:
        raise RuntimeError(str(image.get("error") or "Image endpoint returned no image"))
    annotations: list[dict[str, Any]] = []
    localization_ms = 0.0
    if use_pipeline:
        localized, localization_ms = post_json(f"{interactive_url.rstrip('/')}/localize-structures", {
            "image_base64": image_base64,
            "organ": "heart",
            "view": "anterior_cutaway",
            "speed_mode": "pro",
            "model_variant": "heart_lora" if use_lora else "base",
        })
        annotations = localized.get("annotations") or []
    expected = get_view("heart", "anterior_cutaway")["required_structures"]
    evaluation, eval_ms = post_json(f"{eval_url.rstrip('/')}/evaluate", {
        "image_base64": image_base64,
        "enhanced_prompt": final_prompt if use_pipeline else None,
        "raw_prompt": raw_prompt,
        "anatomy_spec": {**anatomy_spec, "is_anatomy": True, "organ": "heart", "view": "anterior_cutaway", "required_structures": expected},
        "enable_anatomy_critic": True,
    })
    metrics = score_prompt(final_prompt, {**anatomy_spec, "organ": "heart", "view": "anterior_cutaway", "required_structures": expected})
    metrics.update({
        key: value for key, value in (evaluation.get("anatomy_metrics") or {}).items()
        if isinstance(value, (int, float, bool))
    })
    metrics.update(score_svg_layout(annotations, expected) if use_pipeline else {})
    return {
        "variant": variant,
        "seed": seed,
        "raw_prompt": raw_prompt,
        "latency_ms": prompt_ms + image_ms + localization_ms + eval_ms,
        "stage_latency_ms": {"prompt": prompt_ms, "image": image_ms, "localization": localization_ms, "evaluation": eval_ms},
        "metrics": metrics,
        "hard_failures": evaluation.get("anatomy_hard_failures") or [],
        "image_sha_hint": base64.b64decode(image_base64)[:16].hex(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-url", default=os.getenv("PROMPT_AGENT_URL", ""))
    parser.add_argument("--image-url", default=os.getenv("IMAGE_AGENT_URL", ""))
    parser.add_argument("--interactive-url", default=os.getenv("INTERACTIVE_AGENT_URL", ""))
    parser.add_argument("--eval-url", default=os.getenv("EVAL_AGENT_URL", ""))
    parser.add_argument("--output", type=Path, default=HERE / "results.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    if not all((args.prompt_url, args.image_url, args.interactive_url, args.eval_url)):
        parser.error("agent URLs are required through arguments or environment variables")
    suite = json.loads((HERE / "heart_test_prompts.json").read_text(encoding="utf-8"))
    prompts = suite["prompts"][: args.limit or None]
    rows = []
    for case in prompts:
        for seed in suite["fixed_seeds"]:
            for variant in ("raw_base", "agentic_pipeline", "finetuned_pipeline"):
                rows.append(run_case(args.prompt_url, args.image_url, args.interactive_url, args.eval_url, case["prompt"], seed, variant))
    payload = {"protocol": suite["version"], "rows": rows, "summary": aggregate_runs(rows)}
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
