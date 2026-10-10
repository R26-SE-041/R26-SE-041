"""End-to-end turn latency with a per-stage breakdown.

Table 1 gives each agent's latency in isolation. That is not the number a user
feels: a spoken turn runs STT → transcript correction → RAG → localisation →
TTS in sequence, and the interesting question is which stage owns the turn.
This harness answers it by timing the real LangGraph pipeline — the same graph
`POST /api/v1/voice/query` builds — rather than summing Table 1, which would
silently omit retrieval, Chroma, Supabase upload and the graph's own overhead.

It invokes the compiled graph directly, in-process. That deliberately excludes
FastAPI, auth and the browser, so the measurement isolates the AI pipeline; say
so in the paper, and note that the user-visible turn is this plus a fixed
transport cost.

Two properties matter for a defensible number:

  * **Stage timing is exact, not inferred.** Each node is wrapped in a timer
    before the graph is compiled, so a stage's cost is measured where it
    happens rather than reconstructed from log lines.
  * **Warm-up is discarded.** The first turn pays five cold starts across four
    GPU classes and would dominate any average. The paper's claim is about
    steady-state interaction.

The five language paths exercise different models — English routes to Whisper
and Kokoro, Tamil to Qwen3-ASR and IndicF5, Sinhala to whisper-small-sinhala
and SinhalaVITS — so run each separately and report them as separate rows.
A single pooled figure would describe no real user.

Cost warning: one turn touches T4, A10G and A100-80GB. Keep `--runs` small
(3-5 is enough for a stage *share*, which is what the stacked bar shows) and
use `--dry-run` first.

Usage:
    python -m benchmarks.eval_e2e --dry-run
    python -m benchmarks.eval_e2e --language english --runs 3
    python -m benchmarks.eval_e2e --language all --runs 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BENCH_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from benchmarks.latency_bench import (  # noqa: E402
    FIXTURES,
    FIXTURES_DIR,
    resolve_fixture,
    wav_duration_seconds,
)

RESULTS_DIR = BENCH_DIR / "results"

STAGES = ["stt", "prompt_enhancer", "rag", "localization", "tts"]

# Which models each language path actually exercises — recorded alongside the
# timings so a reader can see why the rows differ.
LANGUAGE_PATHS = {
    "english": "Whisper L-V3 (T4) → Gemma corrector (A100) → RAG v2 (A100) → "
               "[no localisation] → Kokoro-82M (CPU)",
    "tamil": "tamil-asr-qwen3 (A10G) → Gemma corrector (A100) → RAG v2 (A100) → "
             "Qwen2.5-7B (T4) → IndicF5 (A10G)",
    "sinhala": "whisper-small-sinhala (T4) → Gemma corrector (A100) → RAG v2 (A100) → "
               "Qwen2.5-7B (T4) → SinhalaVITS-M2 (T4)",
    "mixed": "Whisper L-V3 auto-detect (T4) → Gemma corrector (A100) → RAG v2 (A100) → "
             "Qwen2.5-7B (T4) → Indic Parler (A10G)",
}


def build_timed_graph(timings: dict[str, list[float]]):
    """Compile the production graph with every node wrapped in a timer.

    The wrapper is applied to the node callables before `add_node`, so the graph
    topology and the node implementations are exactly the deployed ones — only
    the clock is added.
    """
    from langgraph.graph import END, StateGraph

    from app.agents.localization_agent import localization_node
    from app.agents.prompt_agent import prompt_agent_node
    from app.agents.rag_agent import rag_agent_node
    from app.agents.stt_agent import stt_node
    from app.agents.tts_agent import tts_node

    nodes = {
        "stt": stt_node,
        "prompt_enhancer": prompt_agent_node,
        "rag": rag_agent_node,
        "localization": localization_node,
        "tts": tts_node,
    }

    def timed(name, func):
        async def wrapper(state: dict) -> dict:
            started = time.perf_counter()
            try:
                return await func(state)
            finally:
                timings.setdefault(name, []).append(
                    (time.perf_counter() - started) * 1000
                )
        return wrapper

    graph = StateGraph(dict)
    for name, func in nodes.items():
        graph.add_node(name, timed(name, func))

    graph.set_entry_point("stt")
    graph.add_edge("stt", "prompt_enhancer")
    graph.add_edge("prompt_enhancer", "rag")
    graph.add_edge("rag", "localization")
    graph.add_edge("localization", "tts")
    graph.add_edge("tts", END)
    return graph.compile()


async def run_language(language: str, runs: int, user_id: str, skip_warmup: bool) -> dict:
    fixture = resolve_fixture(language)
    if fixture is None:
        stem = Path(FIXTURES[language]).stem
        raise FileNotFoundError(
            f"no audio fixture {FIXTURES_DIR / stem}.* — "
            f"drop an 8-12 s {language} clip there"
        )
    audio = fixture.read_bytes()
    audio_seconds = wav_duration_seconds(audio)

    print(f"\n── {language}")
    print(f"   {LANGUAGE_PATHS[language]}")

    record: dict = {
        "language": language,
        "model_path": LANGUAGE_PATHS[language],
        "input_audio_seconds": audio_seconds,
        "runs_requested": runs,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "turns": [],
    }

    def initial_state() -> dict:
        return {
            "audio_bytes": audio,
            "audio_filename": fixture.name,
            "language": language,
            "user_id": user_id,
            "session_id": None,
        }

    if not skip_warmup:
        print("   warm-up turn (discarded, pays up to five cold starts) …",
              end="", flush=True)
        warm_timings: dict[str, list[float]] = {}
        started = time.perf_counter()
        try:
            await build_timed_graph(warm_timings).ainvoke(initial_state())
            record["warmup_ms"] = round((time.perf_counter() - started) * 1000, 1)
            print(f" {record['warmup_ms'] / 1000:.1f}s")
        except Exception as exc:
            record["error"] = f"warm-up failed: {type(exc).__name__}: {exc}"
            print(f" FAILED — {type(exc).__name__}: {exc}")
            return record

    totals: list[float] = []
    stage_timings: dict[str, list[float]] = {}

    for i in range(runs):
        turn_timings: dict[str, list[float]] = {}
        graph = build_timed_graph(turn_timings)
        started = time.perf_counter()
        try:
            result = await graph.ainvoke(initial_state())
        except Exception as exc:
            record["turns"].append({"i": i, "error": f"{type(exc).__name__}: {exc}"})
            print(f"   [{i + 1}/{runs}] FAILED {type(exc).__name__}: {exc}")
            continue
        total_ms = (time.perf_counter() - started) * 1000
        totals.append(total_ms)

        stages = {name: round(vals[0], 1)
                  for name, vals in turn_timings.items() if vals}
        for name, value in stages.items():
            stage_timings.setdefault(name, []).append(value)

        record["turns"].append({
            "i": i,
            "total_ms": round(total_ms, 1),
            "stages_ms": stages,
            "transcript": result.get("transcript", "")[:200],
            "answer_chars": len(result.get("localized_answer")
                                or result.get("answer", "")),
            "audio_url_returned": bool(result.get("audio_url")),
        })
        breakdown = "  ".join(f"{n}={stages.get(n, 0):.0f}" for n in STAGES)
        print(f"   [{i + 1}/{runs}] total {total_ms:7.0f} ms   {breakdown}")

    if totals:
        record["total_ms"] = {
            "n": len(totals),
            "mean": round(statistics.fmean(totals), 1),
            "sd": round(statistics.stdev(totals), 1) if len(totals) > 1 else 0.0,
            "p50": round(sorted(totals)[len(totals) // 2], 1),
            "min": round(min(totals), 1),
            "max": round(max(totals), 1),
        }
        mean_total = statistics.fmean(totals)
        record["stages"] = {
            name: {
                "mean_ms": round(statistics.fmean(vals), 1),
                "share_pct": round(statistics.fmean(vals) / mean_total * 100, 1),
                "n": len(vals),
            }
            for name, vals in stage_timings.items()
        }
        # How much of the turn is unaccounted for by the five nodes: graph
        # overhead, state copying, Supabase upload inside the TTS node.
        accounted = sum(v["mean_ms"] for v in record["stages"].values())
        record["unaccounted_ms"] = round(mean_total - accounted, 1)
        record["unaccounted_pct"] = round(
            (mean_total - accounted) / mean_total * 100, 1)

        print(f"\n   mean turn {mean_total:.0f} ms "
              f"({mean_total / 1000:.1f} s), p50 {record['total_ms']['p50']:.0f} ms")
        for name in STAGES:
            if name in record["stages"]:
                stage = record["stages"][name]
                bar = "█" * max(1, int(stage["share_pct"] / 2))
                print(f"     {name:<16}{stage['mean_ms']:8.0f} ms  "
                      f"{stage['share_pct']:5.1f}%  {bar}")
        print(f"     {'(unaccounted)':<16}{record['unaccounted_ms']:8.0f} ms  "
              f"{record['unaccounted_pct']:5.1f}%")

    return record


async def main_async(args) -> int:
    languages = (["english", "tamil", "sinhala", "mixed"]
                 if args.language == "all"
                 else [l.strip() for l in args.language.split(",")])

    print(f"\nEnd-to-end pipeline benchmark — {len(languages)} language path(s) "
          f"× {args.runs} turn(s)")
    print("Each turn touches T4, A10G and A100-80GB. Warm-up turns are discarded.\n")
    for language in languages:
        fixture = resolve_fixture(language)
        mark = fixture.name if fixture else "MISSING FIXTURE"
        print(f"  {language:<10} {mark:<16} {LANGUAGE_PATHS[language]}")

    if args.dry_run:
        print("\ndry run — no requests issued, no credits spent.")
        return 0

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for language in languages:
        try:
            records.append(
                await run_language(language, args.runs, args.user_id, args.skip_warmup)
            )
        except FileNotFoundError as exc:
            print(f"skip {language}: {exc}")

    if not records:
        print("\nNothing measured.")
        return 1

    out = RESULTS_DIR / "e2e_latency.json"
    out.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "In-process LangGraph invocation. Excludes FastAPI, authentication "
            "and browser transport; the user-visible turn is this plus a fixed "
            "transport cost."
        ),
        "languages": records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", default="english",
                        help="english | tamil | sinhala | mixed | all | comma-separated")
    parser.add_argument("--runs", type=int, default=3,
                        help="measured turns per language after a discarded warm-up")
    parser.add_argument("--user-id", default="benchmark-user",
                        help="user whose ingested documents the RAG stage retrieves from")
    parser.add_argument("--skip-warmup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
