"""ASR baseline comparison: WER, CER and native-script purity per language.

Design rule: **transcribe once, score many times.** Every hypothesis is written
to `results/asr_hyps_<system>.json` as it arrives, and `--offline` recomputes
every metric from those files without touching Modal. Normalisation choices and
metric definitions almost always get revised while a paper is being written;
re-transcribing 300 clips on an A10G each time is the expensive way to discover
that.

Systems under comparison (each only runs if its URL is in backend/.env):

    whisper_large_v3    Whisper Large V3, the zero-shot multilingual baseline
    tamil_qwen3         osmapi/tamil-asr-qwen3, the Tamil system model
    sinhala_whisper     whisper-small-sinhala stage-2, the Sinhala system model
    indicconformer      AI4Bharat IndicConformer 600M, the prior Indic baseline

Metrics, and why each is here:

    CER    the headline for Tamil and Sinhala. Both are agglutinative, so a
           single wrong morpheme condemns a whole word and WER overstates the
           error relative to what a reader actually loses.
    WER    reported alongside for comparability with the ASR literature. A wide
           WER/CER gap is itself a finding about morphological error.
    native-script ratio
           the fraction of output letters in the expected script. Whisper's
           documented Indic failure is romanisation — "Night" for "நாய்" — and
           `whisper_stt.py` ships an ASCII suppress list to prevent it. WER
           cannot show whether that worked: a fully romanised transcript and a
           garbled native one can score identically.
    RTF    wall-clock / audio seconds, for the speed-accuracy trade-off.

Manifest — `data/asr_manifest.jsonl`, one JSON object per line:

    {"id": "ta_001", "audio_path": "fixtures/asr/ta_001.wav",
     "reference": "…", "language": "tamil"}

Use held-out clips: Common Voice ta/si test, FLEURS ta_in/si_lk, plus the
in-house code-switch recordings. 100 utterances per language is the minimum for
a WER confidence interval a reviewer will accept.

Usage:
    python -m benchmarks.eval_asr --systems whisper_large_v3 --languages tamil
    python -m benchmarks.eval_asr --systems all --languages all
    python -m benchmarks.eval_asr --offline           # rescore, no Modal calls
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

from benchmarks.latency_bench import load_env, wav_duration_seconds  # noqa: E402
from benchmarks.metrics import (  # noqa: E402
    bootstrap_ci,
    cer,
    corpus_cer,
    corpus_wer,
    native_script_ratio,
    wer,
)

MANIFEST = BENCH_DIR / "data" / "asr_manifest.jsonl"
RESULTS_DIR = BENCH_DIR / "results"

# system -> (env var, transcript field, extra form fields, supported languages)
SYSTEMS = {
    "whisper_large_v3": {
        "env": "MODAL_WHISPER_URL",
        "field": "transcript",
        "form": lambda lang: {"language_hint": lang},
        "languages": {"english", "tamil", "sinhala", "mixed"},
        "label": "Whisper Large V3 (zero-shot)",
    },
    "tamil_qwen3": {
        "env": "MODAL_INDIC_STT_URL",
        "field": "transcript",
        "form": lambda lang: {"language_hint": "tamil"},
        "languages": {"tamil"},
        "label": "osmapi/tamil-asr-qwen3",
    },
    "sinhala_whisper": {
        "env": "MODAL_SINHALA_ASR_URL",
        "field": "text",
        "form": lambda lang: None,
        "languages": {"sinhala"},
        "label": "whisper-small-sinhala (stage-2 FT)",
    },
    "indicconformer": {
        "env": "MODAL_INDIC_CONFORMER_URL",
        "field": "transcript",
        "form": lambda lang: {"language_hint": lang},
        "languages": {"tamil"},
        "label": "IndicConformer 600M (prior baseline)",
    },
}

SCRIPT_FOR_LANGUAGE = {"tamil": "tamil", "sinhala": "sinhala", "english": "latin"}


def load_manifest(languages: set[str]) -> list[dict]:
    if not MANIFEST.exists():
        raise SystemExit(
            f"No manifest at {MANIFEST}.\n"
            "One JSON object per line: id, audio_path, reference, language.\n"
            "See the module docstring for the recommended corpora."
        )
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        if row["language"] in languages:
            rows.append(row)
    return rows


def transcribe_all(system: str, rows: list[dict], url: str) -> list[dict]:
    """Send every clip once and persist the raw hypothesis."""
    spec = SYSTEMS[system]
    out_path = RESULTS_DIR / f"asr_hyps_{system}.json"
    existing = {}
    if out_path.exists():
        existing = {h["id"]: h for h in json.loads(out_path.read_text(encoding="utf-8"))}

    hypotheses = list(existing.values())
    with httpx.Client(follow_redirects=True, timeout=600.0) as client:
        for i, row in enumerate(rows, start=1):
            if row["id"] in existing:
                continue                      # already transcribed; never pay twice
            audio_path = BENCH_DIR / row["audio_path"]
            if not audio_path.exists():
                print(f"   [{row['id']}] missing audio {audio_path}")
                continue
            audio = audio_path.read_bytes()
            form = spec["form"](row["language"])

            started = time.perf_counter()
            try:
                kwargs = {
                    "files": {"audio_file": (audio_path.name, audio,
                                             "application/octet-stream")},
                }
                if form:
                    kwargs["data"] = form
                    kwargs["params"] = form
                response = client.post(url, **kwargs)
                response.raise_for_status()
                body = response.json()
            except Exception as exc:
                print(f"   [{row['id']}] FAILED {type(exc).__name__}: {exc}")
                continue
            elapsed = time.perf_counter() - started

            hyp = {
                "id": row["id"],
                "language": row["language"],
                "reference": row["reference"],
                "hypothesis": str(body.get(spec["field"], "")).strip(),
                "wall_ms": round(elapsed * 1000, 1),
                "audio_seconds": wav_duration_seconds(audio),
            }
            hypotheses.append(hyp)
            # Write after every clip: a crash at clip 250 must not throw away
            # the GPU time already spent on clips 1-249.
            out_path.write_text(json.dumps(hypotheses, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            print(f"   [{i}/{len(rows)}] {row['id']} {elapsed * 1000:7.0f} ms  "
                  f"{hyp['hypothesis'][:60]}")

    return hypotheses


def score(system: str, hypotheses: list[dict]) -> dict:
    """Compute all metrics for one system, grouped by language."""
    by_language: dict[str, list[dict]] = {}
    for hyp in hypotheses:
        by_language.setdefault(hyp["language"], []).append(hyp)

    report = {"system": system, "label": SYSTEMS[system]["label"], "languages": {}}
    for language, rows in sorted(by_language.items()):
        pairs = [(r["reference"], r["hypothesis"]) for r in rows]
        per_utt_wer = [wer(r, h)["wer"] for r, h in pairs]
        per_utt_cer = [cer(r, h)["cer"] for r, h in pairs]

        script = SCRIPT_FOR_LANGUAGE.get(language)
        script_ratios = (
            [native_script_ratio(r["hypothesis"], script) for r in rows]
            if script else []
        )
        rtfs = [
            r["wall_ms"] / 1000 / r["audio_seconds"]
            for r in rows if r.get("audio_seconds")
        ]

        report["languages"][language] = {
            "n": len(rows),
            "corpus_wer": round(corpus_wer(pairs)["wer"], 4),
            "corpus_cer": round(corpus_cer(pairs)["cer"], 4),
            "wer_ci95": bootstrap_ci(per_utt_wer),
            "cer_ci95": bootstrap_ci(per_utt_cer),
            "native_script_ratio": (
                round(sum(script_ratios) / len(script_ratios), 4) if script_ratios else None
            ),
            "rtf_mean": round(sum(rtfs) / len(rtfs), 3) if rtfs else None,
            "errors": corpus_wer(pairs),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--systems", default="all")
    parser.add_argument("--languages", default="all")
    parser.add_argument("--offline", action="store_true",
                        help="rescore saved hypotheses; issue no requests")
    args = parser.parse_args()

    env = load_env()
    systems = (list(SYSTEMS) if args.systems == "all"
               else [s.strip() for s in args.systems.split(",")])
    languages = ({"english", "tamil", "sinhala", "mixed"} if args.languages == "all"
                 else {l.strip() for l in args.languages.split(",")})

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    reports = []

    for system in systems:
        spec = SYSTEMS[system]
        applicable = languages & spec["languages"]
        if not applicable:
            continue

        if args.offline:
            path = RESULTS_DIR / f"asr_hyps_{system}.json"
            if not path.exists():
                print(f"skip {system}: no saved hypotheses at {path}")
                continue
            hypotheses = json.loads(path.read_text(encoding="utf-8"))
        else:
            url = env.get(spec["env"], "").strip()
            if not url:
                print(f"skip {system}: {spec['env']} not set in backend/.env")
                continue
            rows = load_manifest(applicable)
            if not rows:
                print(f"skip {system}: manifest has no {applicable} clips")
                continue
            print(f"\n── {system} ({spec['label']}) — {len(rows)} clip(s)")
            hypotheses = transcribe_all(system, rows, url)

        hypotheses = [h for h in hypotheses if h["language"] in applicable]
        if not hypotheses:
            continue
        reports.append(score(system, hypotheses))

    if not reports:
        print("\nNothing scored.")
        return 1

    print(f"\n{'system':<22}{'lang':<10}{'WER':>8}{'CER':>8}"
          f"{'script':>9}{'RTF':>7}{'n':>5}")
    for report in reports:
        for language, m in report["languages"].items():
            script = (f"{m['native_script_ratio']:.3f}"
                      if m["native_script_ratio"] is not None else "—")
            rtf = f"{m['rtf_mean']:.2f}" if m["rtf_mean"] is not None else "—"
            print(f"{report['system']:<22}{language:<10}{m['corpus_wer']:>8.3f}"
                  f"{m['corpus_cer']:>8.3f}{script:>9}{rtf:>7}{m['n']:>5}")

    out = RESULTS_DIR / "asr_eval.json"
    out.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "normalisation": "NFC, casefold, punctuation stripped, whitespace collapsed",
        "reports": reports,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
