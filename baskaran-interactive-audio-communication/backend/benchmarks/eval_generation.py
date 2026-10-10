"""Answer-generation comparison: base Gemma vs LoRA v2 vs document-grounded RAG.

This is the most expensive table in the study — three A100-80GB endpoints — so
the harness is built to be paid for exactly once:

  * every generated answer is appended to `results/gen_answers_<system>.json`
    as it arrives, and a re-run skips any question already answered;
  * `--offline` recomputes every metric from those files with no Modal calls;
  * `--limit` caps the question count for a cheap smoke test before committing
    to the full set.

Automatic metrics here are *screening* metrics, and the paper must say so.
ROUGE-L and token-F1 reward surface overlap, and `context_groundedness` counts
how many of the answer's content words appear in the retrieved context — a
lower bound on faithfulness that penalises correct paraphrase. Their job is to
rank the whole set cheaply so that human review and the LLM-judge can be spent
on the disagreements and the low-scoring tail, not to stand in as the headline
quality claim. State the sample size of the human pass alongside them.

Question set — `data/generation_qa.json`:

    {"questions": [
      {"id": "g01",
       "question": "What is the origin of the pectoralis major?",
       "reference_answer": "…",
       "context": ["…", "…"],
       "in_finetune_domain": true}
    ]}

`in_finetune_domain` marks the five LoRA-trained muscles. The headline result is
the interaction: the fine-tune should beat the base model inside its domain
*without* regressing outside it. A single pooled average hides exactly that.

Usage:
    python -m benchmarks.eval_generation --systems base --limit 5
    python -m benchmarks.eval_generation --systems all
    python -m benchmarks.eval_generation --offline
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BENCH_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BENCH_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from benchmarks.latency_bench import load_env  # noqa: E402
from benchmarks.metrics import (  # noqa: E402
    bootstrap_ci,
    context_groundedness,
    rouge_l,
    token_f1,
)

QA = BENCH_DIR / "data" / "generation_qa.json"
RESULTS_DIR = BENCH_DIR / "results"

SYSTEMS = {
    "base": {
        "env": "MODAL_BASE_GEMMA_URL",
        "label": "Gemma-4-12B-it base (no adapter)",
        "route": "document_rag_base",
        "with_context": True,
    },
    "finetuned_v2": {
        "env": "MODAL_FINETUNED_GEMMA_V2_URL",
        "label": "Gemma-4-12B-it + LoRA v2",
        "route": "muscle_finetuned_v2",
        "with_context": False,
    },
    "rag_v2": {
        "env": "MODAL_RAG_GENERATOR_URL",
        "label": "RAG generator v2 (retrieved context)",
        "route": None,                     # rag_generator has no route field
        "with_context": True,
    },
    "closed_book": {
        "env": "MODAL_BASE_GEMMA_URL",
        "label": "Gemma-4-12B-it base, no retrieval",
        "route": "general_base",
        "with_context": False,
    },
}


def build_payload(spec: dict, case: dict) -> dict:
    payload = {
        "query": case["question"],
        "context": case.get("context", []) if spec["with_context"] else [],
        "language": "english",
        "tutor_instructions": "",
        "memento": None,
    }
    if spec["route"]:
        payload["route"] = spec["route"]
    return payload


def generate_all(system: str, cases: list[dict], url: str) -> list[dict]:
    spec = SYSTEMS[system]
    out_path = RESULTS_DIR / f"gen_answers_{system}.json"
    existing = {}
    if out_path.exists():
        existing = {a["id"]: a for a in json.loads(out_path.read_text(encoding="utf-8"))}

    answers = list(existing.values())
    with httpx.Client(follow_redirects=True, timeout=600.0) as client:
        for i, case in enumerate(cases, start=1):
            if case["id"] in existing:
                continue                    # already generated; never pay twice
            started = time.perf_counter()
            try:
                response = client.post(url, json=build_payload(spec, case))
                response.raise_for_status()
                body = response.json()
            except Exception as exc:
                print(f"   [{case['id']}] FAILED {type(exc).__name__}: {exc}")
                continue
            elapsed = time.perf_counter() - started

            record = {
                "id": case["id"],
                "question": case["question"],
                "reference_answer": case["reference_answer"],
                "context": case.get("context", []),
                "in_finetune_domain": case.get("in_finetune_domain", False),
                "answer": str(body.get("answer", "")).strip(),
                "wall_ms": round(elapsed * 1000, 1),
                "server_timings_ms": body.get("timings_ms"),
                "output_tokens": body.get("output_tokens"),
                "gpu": body.get("gpu"),
            }
            answers.append(record)
            out_path.write_text(json.dumps(answers, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            print(f"   [{i}/{len(cases)}] {case['id']} {elapsed * 1000:7.0f} ms  "
                  f"{record['answer'][:70]}")
    return answers


def score_group(records: list[dict]) -> dict:
    if not records:
        return {}
    rouge = [rouge_l(r["reference_answer"], r["answer"])["f1"] for r in records]
    f1 = [token_f1(r["reference_answer"], r["answer"]) for r in records]
    grounded = [
        context_groundedness(r["answer"], r["context"]) for r in records if r["context"]
    ]
    latencies = [r["wall_ms"] for r in records]
    return {
        "n": len(records),
        "rouge_l_f1": round(sum(rouge) / len(rouge), 4),
        "rouge_l_ci95": bootstrap_ci(rouge),
        "token_f1": round(sum(f1) / len(f1), 4),
        "token_f1_ci95": bootstrap_ci(f1),
        "context_groundedness": (
            round(sum(grounded) / len(grounded), 4) if grounded else None
        ),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1),
        "mean_answer_words": round(
            sum(len(r["answer"].split()) for r in records) / len(records), 1
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--systems", default="all")
    parser.add_argument("--limit", type=int, help="cap questions (cheap smoke test)")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    if not QA.exists() and not args.offline:
        raise SystemExit(f"No question set at {QA}. See the module docstring.")

    env = load_env()
    systems = (list(SYSTEMS) if args.systems == "all"
               else [s.strip() for s in args.systems.split(",")])
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = []
    for system in systems:
        spec = SYSTEMS[system]
        if args.offline:
            path = RESULTS_DIR / f"gen_answers_{system}.json"
            if not path.exists():
                print(f"skip {system}: no saved answers at {path}")
                continue
            answers = json.loads(path.read_text(encoding="utf-8"))
        else:
            url = env.get(spec["env"], "").strip()
            if not url:
                print(f"skip {system}: {spec['env']} not set")
                continue
            cases = json.loads(QA.read_text(encoding="utf-8"))["questions"]
            if args.limit:
                cases = cases[: args.limit]
            print(f"\n── {system} ({spec['label']}) — {len(cases)} question(s)")
            answers = generate_all(system, cases, url)

        in_domain = [a for a in answers if a["in_finetune_domain"]]
        out_domain = [a for a in answers if not a["in_finetune_domain"]]
        reports.append({
            "system": system,
            "label": spec["label"],
            "overall": score_group(answers),
            "in_finetune_domain": score_group(in_domain),
            "out_of_domain": score_group(out_domain),
        })

    if not reports:
        print("\nNothing scored.")
        return 1

    print(f"\n{'system':<16}{'split':<20}{'ROUGE-L':>9}{'tok-F1':>9}"
          f"{'ground':>9}{'ms':>9}{'n':>5}")
    for report in reports:
        for split in ("overall", "in_finetune_domain", "out_of_domain"):
            m = report[split]
            if not m:
                continue
            ground = (f"{m['context_groundedness']:.3f}"
                      if m["context_groundedness"] is not None else "—")
            print(f"{report['system']:<16}{split:<20}{m['rouge_l_f1']:>9.3f}"
                  f"{m['token_f1']:>9.3f}{ground:>9}{m['mean_latency_ms']:>9.0f}"
                  f"{m['n']:>5}")

    out = RESULTS_DIR / "generation_eval.json"
    out.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "caveat": (
            "ROUGE-L, token-F1 and context_groundedness are surface-overlap "
            "screening metrics, not faithfulness measurements. Pair them with "
            "the LLM-judge and human pass described in benchmarks/README.md."
        ),
        "reports": reports,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
