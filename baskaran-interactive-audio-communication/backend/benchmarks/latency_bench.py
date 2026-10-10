"""Warm-state latency benchmark for every VoiceLearn Modal agent.

Protocol (this is what goes in the paper's methodology section):

  1. One warm-up request per agent, **discarded**. This absorbs the cold start
     (container schedule + image pull + weight load), which the study excludes
     by design.
  2. N measured requests, issued back-to-back with no pause. Pausing is not a
     neutral choice: four agents run a 60 s `scaledown_window`, so an idle gap
     lets Modal reclaim the container and the next request silently pays a cold
     start that would land in the tail statistics.
  3. Two clocks are recorded per request:
       - `wall_ms`   — client-side, end to end. Includes TLS, Modal's routing
                       layer and JSON transfer. This is what a user experiences.
       - `server_ms` — the endpoint's own timer, where it exposes one. This is
                       compute only.
     Reporting both is what lets the paper separate model cost from platform
     overhead.
  4. Straight after the batch, a `GET /gpu_info` lands on the still-warm
     container and records the physical device name. It adds no cold start.

Every request and every raw response is written to disk, so metrics can be
recomputed later without spending Modal credits a second time.

Usage
-----
    python -m benchmarks.latency_bench --dry-run          # plan + cost, no calls
    python -m benchmarks.latency_bench --agents all
    python -m benchmarks.latency_bench --agents tts_kokoro_en,embed_bge_m3
    python -m benchmarks.latency_bench --agents all --runs 15 --skip-warmup
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Progress output carries box-drawing and warning glyphs, and the Tamil/Sinhala
# benchmark prompts echo back in error messages; the Windows console defaults
# to cp1252 and would abort the run on the first one.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from benchmarks.registry import (  # noqa: E402
    AGENTS,
    AGENTS_BY_KEY,
    Agent,
    gpu_hourly,
)

BENCH_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BENCH_DIR.parent
RESULTS_DIR = BENCH_DIR / "results"
FIXTURES_DIR = BENCH_DIR / "fixtures"
GPU_INFO_URLS = BENCH_DIR / "gpu_info_urls.json"

# Audio fixture expected per ASR language. Any container format the endpoints
# read is fine — wav, webm, ogg, mp3, m4a — but prefer wav: only wav carries a
# duration this harness can parse without ffmpeg, and without a duration there
# is no real-time factor. Keep every clip the same speaker and roughly the same
# length so ASR latencies stay comparable across languages.
FIXTURES = {
    "english": "bench_english.wav",
    "tamil": "bench_tamil.wav",
    "sinhala": "bench_sinhala.wav",
    "mixed": "bench_mixed.wav",
}

# The first measured output from each production TTS route doubles as the
# fixed ASR latency fixture.  This avoids four extra paid synthesis calls while
# keeping the speech content and container format reproducible.
TTS_FIXTURE_OUTPUTS = {
    "tts_kokoro_en": "bench_english.wav",
    "tts_indicf5_ta": "bench_tamil.wav",
    "tts_indic_parler_mixed": "bench_mixed.wav",
    "tts_sinhala_vits": "bench_sinhala.wav",
}

FIXTURE_EXTENSIONS = (".wav", ".webm", ".ogg", ".mp3", ".m4a", ".flac")


def resolve_fixture(language: str) -> Path | None:
    """Find the benchmark clip for a language, whatever container it is in."""
    stem = Path(FIXTURES[language]).stem
    for ext in FIXTURE_EXTENSIONS:
        candidate = FIXTURES_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


# ── env ──────────────────────────────────────────────────────────────────────

def load_env() -> dict[str, str]:
    """Read backend/.env without importing the app (no Supabase/Chroma startup)."""
    env: dict[str, str] = {}
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("MODAL_")})
    return env


# ── helpers ──────────────────────────────────────────────────────────────────

def wav_duration_seconds(payload: bytes) -> float | None:
    """Duration of a RIFF/WAVE payload, or None if it is not parseable.

    Used for the real-time factor (RTF = wall-clock / audio seconds), the
    standard way to compare TTS and ASR speed across models that emit
    different amounts of audio for the same prompt.
    """
    if len(payload) < 44 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        return None
    pos = 12
    sample_rate = channels = bits = None
    while pos + 8 <= len(payload):
        chunk_id = payload[pos:pos + 4]
        (size,) = struct.unpack("<I", payload[pos + 4:pos + 8])
        body = pos + 8
        if chunk_id == b"fmt " and body + 16 <= len(payload):
            _, channels, sample_rate, _, _, bits = struct.unpack(
                "<HHIIHH", payload[body:body + 16]
            )
        elif chunk_id == b"data":
            if not (sample_rate and channels and bits):
                return None
            return size / (sample_rate * channels * (bits // 8))
        pos = body + size + (size % 2)
    return None


def dig(obj: Any, dotted: str) -> Any:
    """Fetch `a.b.c` out of nested dicts, returning None if any hop is missing."""
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def summarise(samples: list[float]) -> dict[str, float]:
    """Descriptive statistics for one latency batch.

    p90/p95 use the nearest-rank method — with N in the 10-20 range that is the
    honest choice; interpolated percentiles invent precision the sample size
    does not support. Report p50 and p95 in the paper, not the mean alone:
    inference latency is right-skewed and the mean hides the tail.
    """
    if not samples:
        return {}
    ordered = sorted(samples)
    n = len(ordered)

    def nearest_rank(p: float) -> float:
        idx = max(1, min(n, int(-(-p * n // 1))))   # ceil(p*n), clamped
        return ordered[idx - 1]

    return {
        "n": n,
        "mean_ms": round(statistics.fmean(ordered), 1),
        "sd_ms": round(statistics.stdev(ordered), 1) if n > 1 else 0.0,
        "p50_ms": round(nearest_rank(0.50), 1),
        "p90_ms": round(nearest_rank(0.90), 1),
        "p95_ms": round(nearest_rank(0.95), 1),
        "min_ms": round(ordered[0], 1),
        "max_ms": round(ordered[-1], 1),
    }


# ── request builders ─────────────────────────────────────────────────────────

def build_request(agent: Agent, url: str) -> tuple[dict[str, Any], bytes | None]:
    """Return httpx.post kwargs for one measured call, plus the fixture bytes."""
    if agent.method == "multipart":
        fixture = resolve_fixture(agent.audio_lang)
        if fixture is None:
            stem = Path(FIXTURES[agent.audio_lang]).stem
            raise FileNotFoundError(
                f"{agent.key}: no audio fixture {FIXTURES_DIR / stem}.* — "
                f"drop an 8-12 s {agent.audio_lang} clip there "
                f"(see benchmarks/README.md)."
            )
        audio = fixture.read_bytes()
        kwargs: dict[str, Any] = {
            "url": url,
            "files": {"audio_file": (fixture.name, audio, "application/octet-stream")},
        }
        if agent.payload:
            kwargs["data"] = dict(agent.payload)
            kwargs["params"] = dict(agent.payload)   # matches modal_client.py
        return kwargs, audio

    return {"url": url, "json": dict(agent.payload or {})}, None


def parse_response(agent: Agent, response: httpx.Response) -> dict[str, Any]:
    """Extract the comparable per-call facts from whatever shape came back."""
    out: dict[str, Any] = {"status": response.status_code}
    content_type = response.headers.get("content-type", "")

    if agent.modality == "tts" or "audio" in content_type:
        audio = response.content
        out["audio_bytes"] = len(audio)
        out["audio_seconds"] = wav_duration_seconds(audio)
        return out

    try:
        body = response.json()
    except Exception:
        out["raw_text"] = response.text[:500]
        return out

    out["body"] = body
    if agent.server_time_key:
        value = dig(body, agent.server_time_key)
        if isinstance(value, (int, float)):
            out["server_ms"] = float(value) * (1000.0 if agent.server_time_unit == "s" else 1.0)
    return out


# ── gpu_info ─────────────────────────────────────────────────────────────────

def derive_gpu_info_url(inference_url: str) -> str | None:
    """Best-effort guess at the sibling `gpu_info` URL.

    Modal names a web endpoint `{workspace}--{app}-{class}-{method}.modal.run`
    and replaces underscores with hyphens, so swapping the trailing method
    segment usually works. It does NOT work once Modal has truncated the name
    and appended a hash (those URLs end in a 6-char hex segment) — for those,
    paste the URL `modal deploy` printed into gpu_info_urls.json.
    """
    if not inference_url.endswith(".modal.run"):
        return None
    host = inference_url.split("//", 1)[-1].split("/", 1)[0]
    stem = host[: -len(".modal.run")]
    head, _, last = stem.rpartition("-")
    if not head:
        return None
    # A trailing 6-char hex segment means Modal truncated and hashed the name;
    # the gpu_info URL has a different hash we cannot compute here.
    if len(last) == 6 and all(c in "0123456789abcdef" for c in last):
        return None
    return f"https://{head}-gpu-info.modal.run"


def fetch_gpu_info(client: httpx.Client, agent: Agent, url: str) -> dict[str, Any]:
    """Ask the warm container what silicon it is actually running on."""
    overrides: dict[str, str] = {}
    if GPU_INFO_URLS.exists():
        overrides = json.loads(GPU_INFO_URLS.read_text(encoding="utf-8"))

    target = overrides.get(agent.key) or derive_gpu_info_url(url)
    if not target:
        return {
            "error": "gpu_info URL unknown",
            "hint": (
                f"Add '{agent.key}': '<url>' to benchmarks/gpu_info_urls.json. "
                "`modal deploy` prints it next to the inference endpoint."
            ),
        }
    try:
        response = client.get(target, timeout=60.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "url": target}


# ── the benchmark ────────────────────────────────────────────────────────────

def bench_agent(
    client: httpx.Client,
    agent: Agent,
    url: str,
    runs: int,
    skip_warmup: bool,
) -> dict[str, Any]:
    print(f"\n── {agent.key} ({agent.stage})")
    print(f"   {agent.model_id} on {agent.requested_gpu}")

    kwargs, audio = build_request(agent, url)
    record: dict[str, Any] = {
        "key": agent.key,
        "stage": agent.stage,
        "model_id": agent.model_id,
        "requested_gpu": agent.requested_gpu,
        "modality": agent.modality,
        "scaledown_window_s": agent.scaledown_window_s,
        "source": agent.source,
        "endpoint_url": url,
        "runs_requested": runs,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "calls": [],
    }
    if audio is not None:
        record["input_audio_seconds"] = wav_duration_seconds(audio)

    if not skip_warmup:
        print("   warm-up (discarded) ...", end="", flush=True)
        t0 = time.perf_counter()
        try:
            warm = client.post(timeout=600.0, **kwargs)
            warm.raise_for_status()
            record["warmup_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            print(f" {record['warmup_ms'] / 1000:.1f}s")
        except Exception as exc:
            record["error"] = f"warm-up failed: {type(exc).__name__}: {exc}"
            print(f" FAILED — {type(exc).__name__}: {exc}")
            return record

    batch_started = time.perf_counter()
    wall_samples: list[float] = []
    server_samples: list[float] = []

    for i in range(runs):
        t0 = time.perf_counter()
        try:
            response = client.post(timeout=600.0, **kwargs)
            wall_ms = (time.perf_counter() - t0) * 1000
            response.raise_for_status()
        except Exception as exc:
            record["calls"].append({"i": i, "error": f"{type(exc).__name__}: {exc}"})
            print(f"   [{i + 1}/{runs}] FAILED {type(exc).__name__}")
            continue

        call = {"i": i, "wall_ms": round(wall_ms, 1)}
        call.update(parse_response(agent, response))
        if i == 0 and agent.key in TTS_FIXTURE_OUTPUTS:
            FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
            fixture_path = FIXTURES_DIR / TTS_FIXTURE_OUTPUTS[agent.key]
            fixture_path.write_bytes(response.content)
            call["saved_asr_fixture"] = str(fixture_path.relative_to(BENCH_DIR))
        record["calls"].append(call)
        wall_samples.append(wall_ms)
        if "server_ms" in call:
            server_samples.append(call["server_ms"])
        print(f"   [{i + 1}/{runs}] {wall_ms:7.1f} ms", flush=True)

    batch_s = time.perf_counter() - batch_started
    record["batch_elapsed_s"] = round(batch_s, 1)
    record["wall"] = summarise(wall_samples)
    if server_samples:
        record["server"] = summarise(server_samples)

    # Modal's scaledown window is an *idle* timeout, not a cap on how long an
    # active batch may run.  These requests are issued back-to-back after one
    # successful discarded warm-up, so even a slow batch remains warm.  Keep
    # the duration/window comparison as audit metadata rather than incorrectly
    # invalidating slow models such as the localizer.
    record["warm_state_valid"] = bool(wall_samples)
    record["continuous_back_to_back"] = True
    if batch_s > agent.scaledown_window_s:
        record["note"] = (
            f"batch duration ({batch_s:.0f}s) exceeded the {agent.scaledown_window_s}s "
            "idle scaledown window, but requests were continuous; no idle gap "
            "occurred after the discarded warm-up."
        )

    # Real-time factor, the standard cross-model speed measure for speech.
    if agent.modality == "tts":
        durations = [c.get("audio_seconds") for c in record["calls"] if c.get("audio_seconds")]
        if durations and wall_samples:
            audio_s = statistics.fmean(durations)
            record["mean_audio_seconds"] = round(audio_s, 3)
            record["rtf"] = round((statistics.fmean(wall_samples) / 1000) / audio_s, 3)
    elif agent.modality == "asr" and record.get("input_audio_seconds") and wall_samples:
        record["rtf"] = round(
            (statistics.fmean(wall_samples) / 1000) / record["input_audio_seconds"], 3
        )

    record["gpu_info"] = fetch_gpu_info(client, agent, url)
    gpu_name = record["gpu_info"].get("gpu_name", "?")
    print(f"   → p50 {record['wall'].get('p50_ms', '?')} ms | "
          f"p95 {record['wall'].get('p95_ms', '?')} ms | GPU: {gpu_name}")
    return record


def estimate_cost(agents: list[Agent], runs: int) -> float:
    """Very rough USD estimate: cold start + (runs+1) calls, generously padded."""
    total = 0.0
    per_call_s = {"asr": 6.0, "tts": 8.0, "embed": 1.0, "rerank": 1.0, "llm": 12.0}
    cold_s = {"T4": 90.0, "A10G": 120.0, "A100-80GB": 240.0, "CPU (4 vCPU)": 40.0}
    for agent in agents:
        seconds = cold_s.get(agent.requested_gpu, 90.0) + (runs + 1) * per_call_s[agent.modality]
        total += seconds / 3600.0 * gpu_hourly(agent.requested_gpu)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", default="all",
                        help="comma-separated agent keys from registry.py, or 'all'")
    parser.add_argument("--runs", type=int, default=10,
                        help="measured calls per agent after the discarded warm-up")
    parser.add_argument("--skip-warmup", action="store_true",
                        help="agent is already warm from a previous run")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and cost estimate; issue no requests")
    parser.add_argument("--out", default=str(RESULTS_DIR))
    args = parser.parse_args()

    env = load_env()
    selected = (
        AGENTS
        if args.agents == "all"
        else [AGENTS_BY_KEY[k.strip()] for k in args.agents.split(",") if k.strip()]
    )

    runnable: list[tuple[Agent, str]] = []
    for agent in selected:
        url = env.get(agent.env_var, "").strip()
        if not url:
            print(f"skip {agent.key}: {agent.env_var} not set in backend/.env")
            continue
        runnable.append((agent, url))

    print(f"\n{len(runnable)} agent(s) × {args.runs} measured runs "
          f"(+1 discarded warm-up each)")
    print(f"estimated Modal cost: ~${estimate_cost([a for a, _ in runnable], args.runs):.2f} "
          f"(order-of-magnitude; cold starts dominate)\n")

    for agent, _ in runnable:
        flag = " ⚠ tight 60s window" if agent.scaledown_window_s <= 60 else ""
        print(f"  {agent.key:26s} {agent.requested_gpu:14s} {agent.stage}{flag}")

    if args.dry_run:
        print("\ndry run — no requests issued, no credits spent.")
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # follow_redirects is required: Modal answers 303 with an attempt token when
    # a container finishes a cold start (see modal_client.py).
    results = []
    with httpx.Client(follow_redirects=True, timeout=600.0) as client:
        for agent, url in runnable:
            try:
                record = bench_agent(client, agent, url, args.runs, args.skip_warmup)
            except FileNotFoundError as exc:
                print(f"skip {agent.key}: {exc}")
                continue
            results.append(record)
            (out_dir / f"latency_{agent.key}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    combined = out_dir / f"latency_all_{stamp}.json"
    combined.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {len(results)} agent record(s) → {out_dir}")
    print(f"combined: {combined}")
    print("next: python -m benchmarks.report --latency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
