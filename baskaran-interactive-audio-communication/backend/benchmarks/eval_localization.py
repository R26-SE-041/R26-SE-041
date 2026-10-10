"""Localisation comparison for en→ta and en→si (Qwen2.5-7B localizer).

Lead with chrF, not BLEU. BLEU tokenises on whitespace, and Tamil and Sinhala
are agglutinative: a correct translation that inflects a word differently scores
near zero on 4-gram precision while remaining perfectly readable. chrF works on
character n-grams, so it is script-aware and tokenisation-free. Report both —
a large BLEU/chrF gap is evidence about morphology, not about quality — but do
not let BLEU carry the claim.

The third metric is the one that matters most for this system. VoiceLearn
translates anatomy tutoring, where the technical terms must survive: an answer
that renders "pectoralis major" as a loose descriptive phrase has failed the
student even if it scores well. `term_preservation` checks each case's expected
terminology explicitly.

Baselines worth including, both free of Modal credits:
  * NLLB-200-distilled-600M — runs on CPU via transformers, the standard open
    MT baseline for low-resource Indic pairs;
  * copy-through — emit the English unchanged. A localiser that cannot beat
    this on chrF is not translating.

Test set — `data/localization_set.json`:

    {"cases": [
      {"id": "l01", "source": "The pectoralis major adducts the humerus.",
       "target_language": "tamil", "reference": "…",
       "must_preserve": ["pectoralis major"]}
    ]}

Usage:
    python -m benchmarks.eval_localization --systems localizer --languages tamil
    python -m benchmarks.eval_localization --systems all
    python -m benchmarks.eval_localization --offline
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
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
    bleu,
    bootstrap_ci,
    chrf,
    corpus_chrf,
    native_script_ratio,
)

DATASET = BENCH_DIR / "data" / "localization_set.json"
RESULTS_DIR = BENCH_DIR / "results"

SYSTEMS = {
    "localizer": {
        "env": "MODAL_LOCALIZER_URL",
        "label": "Qwen2.5-7B-Instruct localizer (deployed)",
        "kind": "modal",
    },
    "copy_through": {
        "env": None,
        "label": "Copy-through (untranslated English)",
        "kind": "identity",
    },
}


def term_preservation(hypothesis: str, must_preserve: list[str]) -> float | None:
    """Fraction of required technical terms that survived translation.

    Matched case-insensitively on the NFC-normalised string, so a term kept in
    Latin script inside Tamil or Sinhala output still counts — which is the
    intended behaviour for anatomical nomenclature.
    """
    if not must_preserve:
        return None
    text = unicodedata.normalize("NFC", hypothesis).casefold()
    hits = sum(1 for term in must_preserve
               if unicodedata.normalize("NFC", term).casefold() in text)
    return round(hits / len(must_preserve), 4)


def translate_all(system: str, cases: list[dict], url: str | None) -> list[dict]:
    spec = SYSTEMS[system]
    out_path = RESULTS_DIR / f"loc_hyps_{system}.json"
    existing = {}
    if out_path.exists():
        existing = {h["id"]: h for h in json.loads(out_path.read_text(encoding="utf-8"))}

    hypotheses = list(existing.values())

    if spec["kind"] == "identity":
        # Costs nothing; regenerate every time rather than caching.
        return [
            {
                "id": c["id"], "target_language": c["target_language"],
                "source": c["source"], "reference": c["reference"],
                "hypothesis": c["source"], "must_preserve": c.get("must_preserve", []),
                "wall_ms": 0.0,
            }
            for c in cases
        ]

    with httpx.Client(follow_redirects=True, timeout=600.0) as client:
        for i, case in enumerate(cases, start=1):
            if case["id"] in existing:
                continue
            started = time.perf_counter()
            try:
                response = client.post(url, json={
                    "text": case["source"],
                    "language": case["target_language"],
                })
                response.raise_for_status()
                body = response.json()
            except Exception as exc:
                print(f"   [{case['id']}] FAILED {type(exc).__name__}: {exc}")
                continue
            elapsed = time.perf_counter() - started

            hypotheses.append({
                "id": case["id"],
                "target_language": case["target_language"],
                "source": case["source"],
                "reference": case["reference"],
                "hypothesis": str(body.get("localized_text", "")).strip(),
                "must_preserve": case.get("must_preserve", []),
                "wall_ms": round(elapsed * 1000, 1),
            })
            out_path.write_text(json.dumps(hypotheses, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            print(f"   [{i}/{len(cases)}] {case['id']} {elapsed * 1000:7.0f} ms")
    return hypotheses


def score(system: str, hypotheses: list[dict]) -> dict:
    by_language: dict[str, list[dict]] = {}
    for hyp in hypotheses:
        by_language.setdefault(hyp["target_language"], []).append(hyp)

    report = {"system": system, "label": SYSTEMS[system]["label"], "languages": {}}
    for language, rows in sorted(by_language.items()):
        references = [r["reference"] for r in rows]
        candidates = [r["hypothesis"] for r in rows]
        per_case_chrf = [chrf(r, h) for r, h in zip(references, candidates)]
        terms = [
            t for t in (term_preservation(r["hypothesis"], r["must_preserve"]) for r in rows)
            if t is not None
        ]
        # A localiser that silently returns the English input is a real failure
        # mode here — modal_client.call_localizer falls back to the original text
        # on any error — and only a script check catches it.
        scripts = [native_script_ratio(h, language) for h in candidates]

        report["languages"][language] = {
            "n": len(rows),
            "chrf": corpus_chrf(references, candidates),
            "chrf_ci95": bootstrap_ci(per_case_chrf),
            "bleu": bleu(references, candidates),
            "term_preservation": round(sum(terms) / len(terms), 4) if terms else None,
            "native_script_ratio": round(sum(scripts) / len(scripts), 4),
            "mean_latency_ms": round(
                sum(r["wall_ms"] for r in rows) / len(rows), 1
            ),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--systems", default="all")
    parser.add_argument("--languages", default="all")
    parser.add_argument("--limit-per-language", type=int,
                        help="pilot cap per target language (credit guard)")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    if not DATASET.exists() and not args.offline:
        raise SystemExit(f"No test set at {DATASET}. See the module docstring.")

    env = load_env()
    systems = (list(SYSTEMS) if args.systems == "all"
               else [s.strip() for s in args.systems.split(",")])
    languages = ({"tamil", "sinhala"} if args.languages == "all"
                 else {l.strip() for l in args.languages.split(",")})
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = []
    for system in systems:
        spec = SYSTEMS[system]
        if args.offline and spec["kind"] == "modal":
            path = RESULTS_DIR / f"loc_hyps_{system}.json"
            if not path.exists():
                print(f"skip {system}: no saved translations at {path}")
                continue
            hypotheses = json.loads(path.read_text(encoding="utf-8"))
        else:
            url = env.get(spec["env"], "").strip() if spec["env"] else None
            if spec["kind"] == "modal" and not url:
                print(f"skip {system}: {spec['env']} not set")
                continue
            # The copy-through arm is generated from the source side, so it needs
            # the test set even in --offline mode.
            if not DATASET.exists():
                print(f"skip {system}: no test set at {DATASET}")
                continue
            cases = [c for c in json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
                     if c["target_language"] in languages]
            if args.limit_per_language:
                counts: dict[str, int] = {}
                limited = []
                for case in cases:
                    language = case["target_language"]
                    if counts.get(language, 0) < args.limit_per_language:
                        limited.append(case)
                        counts[language] = counts.get(language, 0) + 1
                cases = limited
            if not cases:
                print(f"skip {system}: no {languages} cases")
                continue
            print(f"\n── {system} ({spec['label']}) — {len(cases)} case(s)")
            hypotheses = translate_all(system, cases, url)

        hypotheses = [h for h in hypotheses if h["target_language"] in languages]
        if hypotheses:
            reports.append(score(system, hypotheses))

    if not reports:
        print("\nNothing scored.")
        return 1

    print(f"\n{'system':<16}{'lang':<10}{'chrF':>8}{'BLEU':>8}"
          f"{'terms':>8}{'script':>9}{'ms':>9}{'n':>5}")
    for report in reports:
        for language, m in report["languages"].items():
            terms = (f"{m['term_preservation']:.3f}"
                     if m["term_preservation"] is not None else "—")
            print(f"{report['system']:<16}{language:<10}{m['chrf']:>8.2f}"
                  f"{m['bleu']:>8.2f}{terms:>8}{m['native_script_ratio']:>9.3f}"
                  f"{m['mean_latency_ms']:>9.0f}{m['n']:>5}")

    out = RESULTS_DIR / "localization_eval.json"
    out.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "note": "chrF leads; BLEU is reported for comparability only.",
        "reports": reports,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
