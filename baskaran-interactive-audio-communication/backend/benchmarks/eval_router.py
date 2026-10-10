"""Evaluate the deterministic answer router — CPU only, zero Modal credits.

The router in `app/services/model_router.py` decides, before any retrieval or
model call, whether a question goes to the LoRA-tuned muscle adapter, the base
Gemma, or the document-grounded path. Two things make it worth a table of its
own in the paper:

  * It is the system's cost-control mechanism. Every false route to
    `muscle_finetuned_v2` or `document_rag_base` spends A100-80GB time.
  * It is deterministic, so its evaluation is exactly reproducible and free —
    the only component here that can be re-measured at no cost.

The gold labels in `data/router_eval_set.json` encode what the router *should*
do, not what the regex does. That is deliberate: a test set written from the
implementation can only ever score 100% and would tell a reviewer nothing.

Usage:
    python -m benchmarks.eval_router
    python -m benchmarks.eval_router --verbose      # list every misroute
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BENCH_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# The eval set contains Tamil and Sinhala questions; the Windows console
# defaults to cp1252 and would raise UnicodeEncodeError mid-report.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from app.services.model_router import choose_answer_route  # noqa: E402
from benchmarks.metrics import classification_report       # noqa: E402

DATA = BENCH_DIR / "data" / "router_eval_set.json"
RESULTS_DIR = BENCH_DIR / "results"

ROUTES = ["document_rag_base", "muscle_finetuned_v2", "general_base"]

# Routes served by an A100-80GB container. A false positive here is a direct
# credit cost, so the paper reports it separately from ordinary accuracy.
EXPENSIVE_ROUTES = {"muscle_finetuned_v2", "document_rag_base"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="print every misroute")
    parser.add_argument("--out", default=str(RESULTS_DIR))
    args = parser.parse_args()

    payload = json.loads(DATA.read_text(encoding="utf-8"))
    cases = payload["cases"]

    gold: list[str] = []
    predicted: list[str] = []
    per_case = []
    by_category: dict[str, list[bool]] = defaultdict(list)

    for case in cases:
        decision = choose_answer_route(
            case["question"],
            document_grounded=case["document_grounded"],
            memento=case["memento"],
        )
        correct = decision.name == case["gold_route"]
        gold.append(case["gold_route"])
        predicted.append(decision.name)
        by_category[case["category"]].append(correct)
        per_case.append({
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "gold": case["gold_route"],
            "predicted": decision.name,
            "reason": decision.reason,
            "correct": correct,
            "note": case.get("note", ""),
        })

    report = classification_report(gold, predicted, labels=ROUTES)

    # Cost-relevant error split: routing a general question onto an A100 wastes
    # credits; routing a muscle question to the base model wastes the fine-tune.
    over_routes = [c for c in per_case
                   if not c["correct"]
                   and c["predicted"] in EXPENSIVE_ROUTES
                   and c["gold"] == "general_base"]
    under_routes = [c for c in per_case
                    if not c["correct"]
                    and c["gold"] in EXPENSIVE_ROUTES
                    and c["predicted"] == "general_base"]

    category_scores = {
        name: {
            "accuracy": round(sum(hits) / len(hits), 4),
            "n": len(hits),
            "errors": len(hits) - sum(hits),
        }
        for name, hits in sorted(by_category.items())
    }

    print(f"\nRouter evaluation — {report['n']} cases, "
          f"{sum(c['correct'] for c in per_case)} correct")
    print(f"accuracy {report['accuracy']:.3f} | macro-F1 {report['macro_f1']:.3f}\n")

    print(f"{'route':<22}{'P':>8}{'R':>8}{'F1':>8}{'n':>6}")
    for route in ROUTES:
        row = report["per_label"][route]
        print(f"{route:<22}{row['precision']:>8.3f}{row['recall']:>8.3f}"
              f"{row['f1']:>8.3f}{row['support']:>6}")

    print(f"\n{'category':<22}{'acc':>8}{'errors':>8}{'n':>6}")
    for name, row in category_scores.items():
        print(f"{name:<22}{row['accuracy']:>8.3f}{row['errors']:>8}{row['n']:>6}")

    print(f"\nover-routing to a paid A100 path: {len(over_routes)}"
          f"  ({len(over_routes) / len(cases) * 100:.1f}% of all cases)")
    print(f"under-routing away from the fine-tune: {len(under_routes)}")

    if args.verbose or over_routes or under_routes:
        print("\nmisroutes:")
        for case in per_case:
            if case["correct"]:
                continue
            print(f"  [{case['id']}] {case['category']}")
            print(f"      q: {case['question']}")
            print(f"      gold={case['gold']}  predicted={case['predicted']} "
                  f"({case['reason']})")
            if case["note"]:
                print(f"      note: {case['note']}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(DATA.relative_to(BACKEND_DIR)),
        "overall": report,
        "by_category": category_scores,
        "over_routing_to_paid_path": len(over_routes),
        "under_routing_from_finetune": len(under_routes),
        "cases": per_case,
    }
    (out_dir / "router_eval.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nwrote {out_dir / 'router_eval.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
