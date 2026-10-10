"""TTS comparison: round-trip intelligibility, real-time factor, MOS sampling.

The honest position on TTS evaluation is that the claim rests on human MOS, and
no automatic metric substitutes for it. What this harness does is make the human
study affordable and defensible:

  1. **Round-trip intelligibility.** Synthesise the text, send the audio back
     through Whisper Large V3, and score the transcript against the input with
     CER. It measures whether the speech is *decodable*, which is a necessary
     condition for naturalness and a sufficient one for catching real failures —
     wrong language, dropped clauses, garbled phonemes. It is not a naturalness
     score, and the paper must not present it as one.

     The confound to declare: Whisper is itself imperfect on Tamil and Sinhala,
     so round-trip CER is a *joint* measure of the synthesiser and the recogniser.
     It compares TTS systems fairly only when the same ASR scores all of them,
     which is why every arm here is transcribed by the same Whisper endpoint.
     Include the "human speech" control row (`--control`) and the numbers become
     interpretable: it is the floor this ASR imposes, and no TTS can beat it.

  2. **Real-time factor.** Wall-clock ÷ generated audio seconds. The interesting
     comparison is Kokoro on 4 CPU cores against three GPU-served models — for
     an interactive tutor, a CPU model at acceptable RTF changes the deployment
     economics, and that is a result worth its own sentence.

  3. **MOS sampling.** `--sample-mos` writes a randomised, blinded listening
     sheet: clips renamed to opaque ids, a CSV for raters, and a key file kept
     separate. Presentation order is randomised per rater, because a fixed order
     lets raters anchor on whichever system they hear first.

Text set — `data/tts_set.json`:

    {"items": [
      {"id": "t01", "text": "The pectoralis major adducts the humerus.",
       "language": "english"}
    ]}

Usage:
    python -m benchmarks.eval_tts --systems kokoro_en --languages english
    python -m benchmarks.eval_tts --systems all
    python -m benchmarks.eval_tts --transcribe        # round-trip scoring
    python -m benchmarks.eval_tts --sample-mos 20 --raters 15
"""

from __future__ import annotations

import argparse
import json
import random
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
from benchmarks.metrics import bootstrap_ci, cer, corpus_cer, native_script_ratio  # noqa: E402

DATASET = BENCH_DIR / "data" / "tts_set.json"
RESULTS_DIR = BENCH_DIR / "results"
AUDIO_DIR = RESULTS_DIR / "tts_audio"
MOS_DIR = RESULTS_DIR / "mos_study"

SYSTEMS = {
    "kokoro_en": {
        "env": "MODAL_ENGLISH_KOKORO_TTS_URL",
        "label": "Kokoro-82M (CPU)",
        "languages": {"english"},
        "payload": lambda item: {"text": item["text"]},
    },
    "indicf5_ta": {
        "env": "MODAL_TAMIL_TTS_URL",
        "label": "IndicF5 (A10G)",
        "languages": {"tamil"},
        "payload": lambda item: {"text": item["text"], "language": "tamil"},
    },
    "indic_parler_mixed": {
        "env": "MODAL_INDIC_PARLER_MIXED_TTS_URL",
        "label": "Indic Parler-TTS (A10G)",
        "languages": {"tamil", "english", "mixed"},
        "payload": lambda item: {"text": item["text"], "description": ""},
    },
    "sinhala_vits": {
        "env": "MODAL_SINHALA_VITS_TTS_URL",
        "label": "SinhalaVITS-M2 (T4)",
        "languages": {"sinhala"},
        "payload": lambda item: {"text": item["text"]},
    },
    "mms_baseline": {
        "env": "MODAL_TTS_URL",
        "label": "MMS-TTS (baseline, T4)",
        "languages": {"english", "tamil", "sinhala"},
        "payload": lambda item: {"text": item["text"], "language": item["language"]},
    },
}

SCRIPT_FOR_LANGUAGE = {"tamil": "tamil", "sinhala": "sinhala", "english": "latin"}


def synthesise_all(system: str, items: list[dict], url: str) -> list[dict]:
    """Generate audio for every item once, caching to disk."""
    spec = SYSTEMS[system]
    out_path = RESULTS_DIR / f"tts_meta_{system}.json"
    audio_dir = AUDIO_DIR / system
    audio_dir.mkdir(parents=True, exist_ok=True)

    existing = {}
    if out_path.exists():
        existing = {m["id"]: m for m in json.loads(out_path.read_text(encoding="utf-8"))}

    records = list(existing.values())
    with httpx.Client(follow_redirects=True, timeout=600.0) as client:
        for i, item in enumerate(items, start=1):
            if item["id"] in existing:
                continue
            started = time.perf_counter()
            try:
                response = client.post(url, json=spec["payload"](item))
                response.raise_for_status()
                audio = response.content
            except Exception as exc:
                print(f"   [{item['id']}] FAILED {type(exc).__name__}: {exc}")
                continue
            elapsed = time.perf_counter() - started

            audio_path = audio_dir / f"{item['id']}.wav"
            audio_path.write_bytes(audio)
            seconds = wav_duration_seconds(audio)

            records.append({
                "id": item["id"],
                "language": item["language"],
                "text": item["text"],
                "audio_path": str(audio_path.relative_to(BENCH_DIR)),
                "audio_bytes": len(audio),
                "audio_seconds": seconds,
                "wall_ms": round(elapsed * 1000, 1),
                "rtf": round((elapsed / seconds), 3) if seconds else None,
            })
            out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            rtf = f"{records[-1]['rtf']:.2f}" if records[-1]["rtf"] else "?"
            print(f"   [{i}/{len(items)}] {item['id']} {elapsed * 1000:7.0f} ms  "
                  f"{seconds or 0:.1f}s audio  RTF {rtf}")
    return records


def transcribe_back(system: str, records: list[dict], whisper_url: str) -> list[dict]:
    """Round-trip: send generated audio through Whisper, cache the transcript."""
    out_path = RESULTS_DIR / f"tts_roundtrip_{system}.json"
    existing = {}
    if out_path.exists():
        existing = {r["id"]: r for r in json.loads(out_path.read_text(encoding="utf-8"))}

    results = list(existing.values())
    with httpx.Client(follow_redirects=True, timeout=600.0) as client:
        for i, record in enumerate(records, start=1):
            if record["id"] in existing:
                continue
            audio_path = BENCH_DIR / record["audio_path"]
            if not audio_path.exists():
                continue
            hint = record["language"] if record["language"] != "mixed" else "mixed"
            try:
                response = client.post(
                    whisper_url,
                    files={"audio_file": (audio_path.name, audio_path.read_bytes(),
                                          "application/octet-stream")},
                    data={"language_hint": hint},
                    params={"language_hint": hint},
                )
                response.raise_for_status()
                transcript = str(response.json().get("transcript", "")).strip()
            except Exception as exc:
                print(f"   [{record['id']}] ASR FAILED {type(exc).__name__}: {exc}")
                continue

            results.append({
                "id": record["id"],
                "language": record["language"],
                "text": record["text"],
                "transcript": transcript,
            })
            out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            print(f"   [{i}/{len(records)}] {record['id']} → {transcript[:60]}")
    return results


def score(system: str, records: list[dict], roundtrip: list[dict]) -> dict:
    by_id = {r["id"]: r for r in roundtrip}
    by_language: dict[str, list[dict]] = {}
    for record in records:
        by_language.setdefault(record["language"], []).append(record)

    report = {"system": system, "label": SYSTEMS[system]["label"], "languages": {}}
    for language, rows in sorted(by_language.items()):
        rtfs = [r["rtf"] for r in rows if r.get("rtf")]
        durations = [r["audio_seconds"] for r in rows if r.get("audio_seconds")]

        pairs = [
            (r["text"], by_id[r["id"]]["transcript"])
            for r in rows if r["id"] in by_id
        ]
        per_item_cer = [cer(t, h)["cer"] for t, h in pairs]
        script = SCRIPT_FOR_LANGUAGE.get(language)
        scripts = (
            [native_script_ratio(by_id[r["id"]]["transcript"], script)
             for r in rows if r["id"] in by_id]
            if script else []
        )

        report["languages"][language] = {
            "n": len(rows),
            "n_roundtrip": len(pairs),
            "roundtrip_cer": round(corpus_cer(pairs)["cer"], 4) if pairs else None,
            "roundtrip_cer_ci95": bootstrap_ci(per_item_cer) if per_item_cer else None,
            "roundtrip_script_ratio": (
                round(sum(scripts) / len(scripts), 4) if scripts else None
            ),
            "rtf_mean": round(sum(rtfs) / len(rtfs), 3) if rtfs else None,
            "mean_audio_seconds": (
                round(sum(durations) / len(durations), 2) if durations else None
            ),
            "mean_latency_ms": round(sum(r["wall_ms"] for r in rows) / len(rows), 1),
        }
    return report


def build_mos_study(clips_per_system: int, raters: int, seed: int = 20260903) -> None:
    """Write a blinded, order-randomised listening study.

    Blinding and per-rater order randomisation are not paperwork: an unblinded
    sheet invites the rater to score the system they expect to win, and a fixed
    order lets them anchor on whatever they hear first. The key file is written
    separately so the sheets can be handed out without leaking the mapping.
    """
    rng = random.Random(seed)

    pool = []
    for system in SYSTEMS:
        meta_path = RESULTS_DIR / f"tts_meta_{system}.json"
        if not meta_path.exists():
            continue
        records = json.loads(meta_path.read_text(encoding="utf-8"))
        rng.shuffle(records)
        for record in records[:clips_per_system]:
            pool.append({"system": system, **record})

    if not pool:
        print("No synthesised audio found. Run the synthesis pass first.")
        return

    MOS_DIR.mkdir(parents=True, exist_ok=True)

    key = []
    for index, entry in enumerate(pool):
        blind_id = f"clip_{index:03d}"
        key.append({
            "blind_id": blind_id,
            "system": entry["system"],
            "item_id": entry["id"],
            "language": entry["language"],
            "audio_path": entry["audio_path"],
            "text": entry["text"],
        })
    (MOS_DIR / "key.json").write_text(
        json.dumps(key, indent=2, ensure_ascii=False), encoding="utf-8")

    for rater in range(1, raters + 1):
        order = list(key)
        rng.shuffle(order)
        lines = ["blind_id,language,naturalness_1_to_5,intelligibility_1_to_5,notes"]
        lines += [f"{row['blind_id']},{row['language']},,," for row in order]
        (MOS_DIR / f"rater_{rater:02d}.csv").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nMOS study written to {MOS_DIR}")
    print(f"  {len(pool)} clips across {len({k['system'] for k in key})} system(s)")
    print(f"  {raters} rater sheet(s), independently randomised")
    print("  key.json maps blind ids back to systems — do not hand this to raters.")
    print("\nReport mean MOS with 95% CI per system, and inter-rater agreement "
          "(Krippendorff's alpha or intraclass correlation).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--systems", default="all")
    parser.add_argument("--languages", default="all")
    parser.add_argument("--transcribe", action="store_true",
                        help="round-trip generated audio through Whisper and score CER")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--sample-mos", type=int, metavar="N",
                        help="build a blinded MOS listening study with N clips per system")
    parser.add_argument("--raters", type=int, default=15)
    args = parser.parse_args()

    if args.sample_mos:
        build_mos_study(args.sample_mos, args.raters)
        return 0

    env = load_env()
    systems = (list(SYSTEMS) if args.systems == "all"
               else [s.strip() for s in args.systems.split(",")])
    languages = ({"english", "tamil", "sinhala", "mixed"} if args.languages == "all"
                 else {l.strip() for l in args.languages.split(",")})
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    whisper_url = env.get("MODAL_WHISPER_URL", "").strip()
    if args.transcribe and not whisper_url:
        raise SystemExit("MODAL_WHISPER_URL required for round-trip scoring.")

    reports = []
    for system in systems:
        spec = SYSTEMS[system]
        applicable = languages & spec["languages"]
        if not applicable:
            continue

        meta_path = RESULTS_DIR / f"tts_meta_{system}.json"
        if args.offline:
            if not meta_path.exists():
                print(f"skip {system}: no saved audio metadata at {meta_path}")
                continue
            records = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            url = env.get(spec["env"], "").strip()
            if not url:
                print(f"skip {system}: {spec['env']} not set")
                continue
            if not DATASET.exists():
                raise SystemExit(f"No text set at {DATASET}. See the module docstring.")
            items = [i for i in json.loads(DATASET.read_text(encoding="utf-8"))["items"]
                     if i["language"] in applicable]
            if not items:
                print(f"skip {system}: no {applicable} items")
                continue
            print(f"\n── {system} ({spec['label']}) — {len(items)} item(s)")
            records = synthesise_all(system, items, url)

        records = [r for r in records if r["language"] in applicable]
        if not records:
            continue

        roundtrip_path = RESULTS_DIR / f"tts_roundtrip_{system}.json"
        if args.transcribe:
            print(f"   round-trip through Whisper …")
            roundtrip = transcribe_back(system, records, whisper_url)
        elif roundtrip_path.exists():
            roundtrip = json.loads(roundtrip_path.read_text(encoding="utf-8"))
        else:
            roundtrip = []

        reports.append(score(system, records, roundtrip))

    if not reports:
        print("\nNothing scored.")
        return 1

    print(f"\n{'system':<20}{'lang':<10}{'RT-CER':>9}{'script':>9}"
          f"{'RTF':>7}{'audio_s':>9}{'ms':>9}{'n':>5}")
    for report in reports:
        for language, m in report["languages"].items():
            rt = f"{m['roundtrip_cer']:.3f}" if m["roundtrip_cer"] is not None else "—"
            sc = (f"{m['roundtrip_script_ratio']:.3f}"
                  if m["roundtrip_script_ratio"] is not None else "—")
            rtf = f"{m['rtf_mean']:.2f}" if m["rtf_mean"] is not None else "—"
            aud = f"{m['mean_audio_seconds']:.1f}" if m["mean_audio_seconds"] else "—"
            print(f"{report['system']:<20}{language:<10}{rt:>9}{sc:>9}"
                  f"{rtf:>7}{aud:>9}{m['mean_latency_ms']:>9.0f}{m['n']:>5}")

    out = RESULTS_DIR / "tts_eval.json"
    out.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "caveat": (
            "Round-trip CER is a joint measure of the synthesiser and Whisper "
            "Large V3, not a naturalness score. It is comparable across the "
            "systems here only because the same ASR transcribes all of them. "
            "The naturalness claim rests on the MOS study (--sample-mos)."
        ),
        "reports": reports,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
