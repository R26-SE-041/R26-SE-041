"""Paired held-out evaluation for base Qwen versus the anatomy LoRA."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


def _mean(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.fmean(clean) if clean else None


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = q * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def _parse_json(text: str) -> dict[str, Any] | None:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(clean)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start, end = clean.find("{"), clean.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(clean[start:end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None


def _score(parsed: dict[str, Any] | None, expected: dict[str, Any], known: dict[str, set[str]], trigger: str | None = None) -> tuple[dict[str, float | None], list[str]]:
    expected_spec = expected["anatomy_spec"]
    expected_anatomy = bool(expected_spec.get("is_anatomy"))
    if parsed is None:
        return {
            "json_valid": 0.0, "routing_accuracy": 0.0, "organ_accuracy": 0.0 if expected_anatomy else None,
            "view_accuracy": 0.0 if expected_anatomy else None, "structure_precision": 0.0 if expected_anatomy else None,
            "structure_recall": 0.0 if expected_anatomy else None, "canonical_validity": 0.0 if expected_anatomy else None,
            "focus_precision": 0.0 if expected_anatomy else None, "focus_recall": 0.0 if expected_anatomy else None,
            "grade_accuracy": 0.0 if expected_anatomy else None, "detail_accuracy": 0.0 if expected_anatomy else None,
            "orientation_accuracy": 0.0 if expected_anatomy else None,
            "show_flow_accuracy": 0.0 if expected_anatomy else None, "contract_accuracy": 0.0,
            "composite_accuracy": 0.0,
        }, ["invalid_json"]
    predicted_spec = parsed.get("anatomy_spec") if isinstance(parsed.get("anatomy_spec"), dict) else {}
    predicted_anatomy = bool(predicted_spec.get("is_anatomy"))
    routing = float(predicted_anatomy == expected_anatomy)
    metrics: dict[str, float | None] = {"json_valid": 1.0, "routing_accuracy": routing}
    failures: list[str] = []
    if not expected_anatomy:
        if predicted_anatomy:
            failures.append("generic_prompt_misrouted_to_anatomy")
        metrics.update({name: None for name in (
            "organ_accuracy", "view_accuracy", "structure_precision", "structure_recall", "canonical_validity",
            "focus_precision", "focus_recall", "grade_accuracy", "detail_accuracy", "orientation_accuracy",
            "show_flow_accuracy", "contract_accuracy",
        )})
        metrics["composite_accuracy"] = _mean([metrics["json_valid"], routing])
        return metrics, failures
    organ = str(expected_spec["organ"])
    predicted_ids = {str(value) for value in predicted_spec.get("required_structures") or []}
    expected_ids = {str(value) for value in expected_spec.get("required_structures") or []}
    predicted_focus = {str(value) for value in predicted_spec.get("focus_structures") or []}
    expected_focus = {str(value) for value in expected_spec.get("focus_structures") or []}
    organ_accuracy = float(predicted_spec.get("organ") == organ)
    view_accuracy = float(predicted_spec.get("view") == expected_spec.get("view"))
    precision = len(predicted_ids & expected_ids) / len(predicted_ids) if predicted_ids else 0.0
    recall = len(predicted_ids & expected_ids) / len(expected_ids) if expected_ids else 1.0
    canonical = float(bool(predicted_ids) and predicted_ids.issubset(known[organ]))
    focus_precision = len(predicted_focus & expected_focus) / len(predicted_focus) if predicted_focus else float(not expected_focus)
    focus_recall = len(predicted_focus & expected_focus) / len(expected_focus) if expected_focus else float(not predicted_focus)
    grade_accuracy = float(predicted_spec.get("grade_level") == expected_spec.get("grade_level"))
    detail_accuracy = float(predicted_spec.get("detail_level") == expected_spec.get("detail_level"))
    orientation_accuracy = float(predicted_spec.get("orientation") == expected_spec.get("orientation"))
    flow_accuracy = float(bool(predicted_spec.get("show_flow")) == bool(expected_spec.get("show_flow")))
    contract_accuracy = float(set(parsed) == {"anatomy_spec"})
    metrics.update({
        "organ_accuracy": organ_accuracy,
        "view_accuracy": view_accuracy,
        "structure_precision": precision,
        "structure_recall": recall,
        "canonical_validity": canonical,
        "focus_precision": focus_precision,
        "focus_recall": focus_recall,
        "grade_accuracy": grade_accuracy,
        "detail_accuracy": detail_accuracy,
        "orientation_accuracy": orientation_accuracy,
        "show_flow_accuracy": flow_accuracy,
        "contract_accuracy": contract_accuracy,
    })
    if not organ_accuracy:
        failures.append("wrong_organ")
    if not view_accuracy:
        failures.append("wrong_view")
    if not canonical:
        failures.append("unknown_or_empty_structure_ids")
    if recall < 0.8:
        failures.append("low_structure_recall")
    if not contract_accuracy:
        failures.append("anatomy_contract_violation")
    metrics["composite_accuracy"] = _mean(list(metrics.values()))
    return metrics, failures


def _load_test(path: Path, limit: int, seed: int) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if limit and limit < len(rows):
        rng = random.Random(seed)
        by_organ: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_organ[str(row.get("organ") or "generic")].append(row)
        selected = []
        per_group = max(1, limit // len(by_organ))
        for group in sorted(by_organ):
            selected.extend(rng.sample(by_organ[group], min(per_group, len(by_organ[group]))))
        rows = selected[:limit]
    return sorted(rows, key=lambda row: row["id"])


def _generate(model: Any, tokenizer: Any, row: dict[str, Any], max_new_tokens: int) -> tuple[str, float]:
    import torch

    prompt = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    torch.cuda.synchronize()
    latency_ms = (time.perf_counter() - started) * 1000
    new_tokens = output[0, inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True), latency_ms


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = sorted({name for row in rows for name in row["metrics"]})
    latencies = [float(row["latency_ms"]) for row in rows]
    return {
        "count": len(rows),
        "metrics": {name: _mean([row["metrics"].get(name) for row in rows]) for name in metric_names},
        "hard_failure_rate": _mean([float(bool(row["hard_failures"])) for row in rows]),
        "latency_ms": {"mean": _mean(latencies), "p50": _percentile(latencies, 0.5), "p95": _percentile(latencies, 0.95)},
    }


def _bootstrap_delta(base: list[dict[str, Any]], lora: list[dict[str, Any]], metric: str, seed: int, samples: int = 2000) -> dict[str, float]:
    paired = [(float(left["metrics"][metric]), float(right["metrics"][metric])) for left, right in zip(base, lora)]
    observed = statistics.fmean(right - left for left, right in paired)
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        sample = [paired[rng.randrange(len(paired))] for _ in paired]
        deltas.append(statistics.fmean(right - left for left, right in sample))
    return {"mean_delta": observed, "ci95_low": _percentile(deltas, 0.025), "ci95_high": _percentile(deltas, 0.975)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-file", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("prompt_eval_results"))
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--limit", type=int, default=0, help="Balanced pilot size; 0 evaluates all 450")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--seed", type=int, default=26041)
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    assert torch.cuda.is_available(), "A CUDA GPU is required"
    rows = _load_test(args.test_file, args.limit, args.seed)
    known: dict[str, set[str]] = {}
    # Test targets contain the complete canonical vocabulary needed for scoring.
    for row in rows:
        if not row.get("organ"):
            continue
        target = json.loads(row["messages"][2]["content"])
        organ = str(row["organ"])
        known.setdefault(organ, set()).update(row.get("allowed_structure_ids") or target["anatomy_spec"]["required_structures"])
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(args.base_model, quantization_config=quantization, device_map={"": 0})
    model.eval()

    all_results: dict[str, list[dict[str, Any]]] = {}
    for variant in ("base", "anatomy_lora"):
        if variant == "anatomy_lora":
            model = PeftModel.from_pretrained(model, str(args.adapter))
            model.eval()
        _generate(model, tokenizer, rows[0], min(32, args.max_new_tokens))  # warm-up; not measured
        variant_rows = []
        for index, row in enumerate(rows, start=1):
            text, latency_ms = _generate(model, tokenizer, row, args.max_new_tokens)
            expected = json.loads(row["messages"][2]["content"])
            metrics, failures = _score(_parse_json(text), expected, known)
            variant_rows.append({
                "id": row["id"], "organ": row.get("organ") or "generic", "variant": variant,
                "latency_ms": latency_ms, "metrics": metrics, "hard_failures": failures, "raw_output": text,
            })
            if index % 25 == 0:
                print(f"{variant}: {index}/{len(rows)}")
        all_results[variant] = variant_rows

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for variant, variant_rows in all_results.items():
        (args.output_dir / f"{variant}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in variant_rows), encoding="utf-8"
        )
    summary = {
        "base": _summarize(all_results["base"]),
        "anatomy_lora": _summarize(all_results["anatomy_lora"]),
        "paired_composite_delta": _bootstrap_delta(all_results["base"], all_results["anatomy_lora"], "composite_accuracy", args.seed),
        "per_organ": {},
    }
    for organ in sorted({row["organ"] for row in all_results["base"]}):
        summary["per_organ"][organ] = {
            variant: _summarize([row for row in variant_rows if row["organ"] == organ])
            for variant, variant_rows in all_results.items()
        }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
