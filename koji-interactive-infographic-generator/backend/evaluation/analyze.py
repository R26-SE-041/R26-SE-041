"""Generate CSV and JSON summaries with paired tests against full EduVision."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any

METRICS = ("visual_score", "pedagogical_score", "clip_score", "retry_count", "latency_ms")


def _summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values),
        "mean": round(mean(values), 4) if values else None,
        "std": round(stdev(values), 4) if len(values) > 1 else 0.0 if values else None,
    }


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if not row.get("error")]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in valid:
        grouped[row["config_id"]].append(row)
    result: dict[str, Any] = {"configs": {}, "paired_vs_E": {}, "failed_runs": len(rows) - len(valid)}
    for config_id, config_rows in sorted(grouped.items()):
        result["configs"][config_id] = {
            metric: _summary([float(row[metric]) for row in config_rows if row.get(metric) is not None])
            for metric in METRICS
        }

    full = {(row["prompt_id"], int(row["seed"])): row for row in grouped.get("E", [])}
    try:
        from scipy.stats import ttest_rel
    except ImportError:
        ttest_rel = None
    for config_id, config_rows in sorted(grouped.items()):
        if config_id == "E":
            continue
        comparisons: dict[str, Any] = {}
        lookup = {(row["prompt_id"], int(row["seed"])): row for row in config_rows}
        shared = sorted(set(full) & set(lookup))
        for metric in ("visual_score", "pedagogical_score", "clip_score"):
            pairs = [
                (float(lookup[key][metric]), float(full[key][metric]))
                for key in shared
                if lookup[key].get(metric) is not None and full[key].get(metric) is not None
            ]
            if len(pairs) < 2 or ttest_rel is None:
                comparisons[metric] = {"n": len(pairs), "t_stat": None, "p_value": None}
            else:
                statistic = ttest_rel([pair[0] for pair in pairs], [pair[1] for pair in pairs])
                t_stat = float(statistic.statistic)
                p_value = float(statistic.pvalue)
                comparisons[metric] = {
                    "n": len(pairs),
                    "t_stat": round(t_stat, 6) if math.isfinite(t_stat) else None,
                    "p_value": round(p_value, 8) if math.isfinite(p_value) else None,
                }
        result["paired_vs_E"][config_id] = comparisons
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = analyze(rows)
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = args.output_prefix.with_suffix(".json")
    csv_path = args.output_prefix.with_suffix(".csv")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["config", "metric", "n", "mean", "std"])
        for config_id, metrics in report["configs"].items():
            for metric, values in metrics.items():
                writer.writerow([config_id, metric, values["n"], values["mean"], values["std"]])
    print(f"Wrote {json_path} and {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
