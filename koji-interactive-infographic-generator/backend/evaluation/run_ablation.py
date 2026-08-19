"""Run resumable, seed-controlled ablations against the deployed orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.configs import CONFIGS
from evaluation.dataset import build_dataset


def _completed_keys(path: Path) -> tuple[set[tuple[str, str, int]], str | None]:
    keys: set[tuple[str, str, int]] = set()
    experiment_id = None
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            experiment_id = experiment_id or row.get("experiment_id")
            keys.add((row["config_id"], row["prompt_id"], int(row["seed"])))
    return keys, experiment_id


def run_one(
    orchestrator_url: str,
    experiment_id: str,
    config_id: str,
    config: dict[str, bool],
    prompt: dict[str, Any],
    seed: int,
    speed_mode: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    error = None
    payload: dict[str, Any] = {}
    try:
        response = requests.post(
            orchestrator_url.rstrip("/") + "/generate",
            json={
                "prompt": prompt["prompt"],
                "speed_mode": speed_mode,
                "experiment": {
                    "config_id": config_id,
                    **config,
                    "persist_run": False,
                    "seed": seed,
                },
            },
            timeout=900,
        )
        response.raise_for_status()
        payload = response.json()
        error = payload.get("error")
    except Exception as exc:
        error = str(exc)
    scores = payload.get("eval_scores") or {}
    return {
        "experiment_id": experiment_id,
        "config_id": config_id,
        "prompt_id": prompt["prompt_id"],
        "subject": prompt["subject"],
        "grade_level": prompt["grade_level"],
        "prompt": prompt["prompt"],
        "seed": seed,
        "visual_score": scores.get("visual_score"),
        "pedagogical_score": scores.get("pedagogical_score"),
        "clip_score": scores.get("clip_score"),
        "retry_count": payload.get("retry_count", 0),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "error": error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("ORCHESTRATOR_URL"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--configs", nargs="+", choices=sorted(CONFIGS), default=list(CONFIGS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--speed-mode", choices=["normal", "pro", "promax"], default="normal")
    parser.add_argument("--store-db", action="store_true")
    args = parser.parse_args()
    if not args.url:
        parser.error("--url or ORCHESTRATOR_URL is required")
    if args.limit < 1 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    completed, existing_id = _completed_keys(args.output)
    experiment_id = existing_id or str(uuid.uuid4())
    dataset = build_dataset()[:args.limit]
    total = len(args.configs) * len(args.seeds) * len(dataset)
    finished = 0
    with args.output.open("a", encoding="utf-8") as output:
        for config_id in args.configs:
            for prompt in dataset:
                for seed in args.seeds:
                    key = (config_id, prompt["prompt_id"], seed)
                    if key in completed:
                        finished += 1
                        continue
                    result = run_one(
                        args.url, experiment_id, config_id, CONFIGS[config_id],
                        prompt, seed, args.speed_mode,
                    )
                    output.write(json.dumps(result, ensure_ascii=False) + "\n")
                    output.flush()
                    if args.store_db:
                        from shared.db import insert_ablation_result
                        insert_ablation_result(result)
                    finished += 1
                    print(f"[{finished}/{total}] {config_id} {prompt['prompt_id']} seed={seed} error={bool(result['error'])}")
    print(f"Experiment {experiment_id} complete: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

