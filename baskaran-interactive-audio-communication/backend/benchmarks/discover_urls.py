"""Resolve every deployed `gpu_info` endpoint URL via the Modal control plane.

Modal builds a web endpoint's hostname from the workspace, app, class and
method names, then truncates and hash-suffixes it once it grows too long. That
suffix is not derivable locally, so roughly half of this project's endpoints
cannot have their `gpu_info` URL guessed from the inference URL — they would
otherwise have to be copied by hand out of `modal deploy` output, fifteen times,
without typos.

This asks Modal instead. `modal.Cls.from_name(...)` is a **control-plane
lookup**: it reads deployment metadata and does not start a container, so it
spawns no GPU and costs nothing. It does require the endpoints to be deployed
and `modal` to be authenticated (`modal token new`).

Usage:
    python -m benchmarks.discover_urls            # write gpu_info_urls.json
    python -m benchmarks.discover_urls --print    # show, do not write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

OUTPUT = BENCH_DIR / "gpu_info_urls.json"

# registry key -> (Modal app name, class name), matching the deployed apps in
# backend/modal_endpoints/.
#
# Five of these app names are `os.environ.get("VOICELEARN_*_APP_NAME", default)`
# in the source, so the names below are the defaults. If any of those variables
# was set at deploy time, the lookup fails with NotFound and the failure list
# tells you which one — set the same variable here, or paste that URL by hand.
TARGETS: dict[str, tuple[str, str]] = {
    "asr_whisper_en": ("voicelearn-whisper-stt", "WhisperSTT"),
    "asr_whisper_mixed": ("voicelearn-whisper-stt", "WhisperSTT"),
    "asr_tamil_qwen3": ("voicelearn-tamil-asr-qwen3", "TamilASRQwen3"),
    "asr_sinhala_whisper": ("voicelearn-sinhala-whisper-asr-stage2", "SinhalaWhisperASR"),
    "asr_indicconformer": ("voicelearn-indic-stt", "IndicSTT"),
    "embed_bge_m3": ("voicelearn-bge-retrieval", "BGEEmbedder"),
    "rerank_bge_v2_m3": ("voicelearn-bge-retrieval", "BGEReranker"),
    "llm_rag_generator_v2": ("voicelearn-rag-generator-v2", "RAGGenerator"),
    "llm_transcript_corrector": ("voicelearn-rag-generator-v2", "RAGGenerator"),
    "llm_gemma_base": ("voicelearn-hybrid-gemma", "BaseGemmaAnswer"),
    "llm_gemma_finetuned_v2": ("voicelearn-hybrid-gemma", "FineTunedGemmaV2Answer"),
    "llm_localizer": ("voicelearn-localizer", "Localizer"),
    "tts_kokoro_en": ("voicelearn-english-kokoro-tts", "EnglishKokoroTTS"),
    "tts_indicf5_ta": ("voicelearn-tamil-parler-tts", "TamilIndicF5TTS"),
    "tts_indic_parler_mixed": ("voicelearn-indic-parler-mixed-tts", "IndicParlerMixedTTS"),
    "tts_sinhala_vits": ("voicelearn-sinhala-vits-tts", "SinhalaVITSTTS"),
    "tts_mms_baseline": ("voicelearn-tts", "MMSTTS"),
}


def web_url_for(app_name: str, class_name: str, method: str = "gpu_info") -> str:
    """Look up one deployed method's public URL. Starts no container."""
    import modal

    cls = modal.Cls.from_name(app_name, class_name)
    handle = getattr(cls, method)
    for attribute in ("web_url", "get_web_url"):
        value = getattr(handle, attribute, None)
        if callable(value):
            value = value()
        if value:
            return str(value)
    raise RuntimeError(
        f"{app_name}/{class_name}.{method} exposes no web URL — is the newest "
        "version deployed?"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", dest="print_only", action="store_true")
    parser.add_argument("--method", default="gpu_info")
    args = parser.parse_args()

    resolved: dict[str, str] = {}
    failures: dict[str, str] = {}

    # Several registry keys share one deployed class (the two Whisper language
    # modes, the RAG generator's two endpoints). Look each class up once.
    cache: dict[tuple[str, str], str] = {}

    for key, (app_name, class_name) in TARGETS.items():
        pair = (app_name, class_name)
        if pair in cache:
            resolved[key] = cache[pair]
            print(f"  {key:26s} (cached) {cache[pair]}")
            continue
        try:
            url = web_url_for(app_name, class_name, args.method)
        except Exception as exc:
            failures[key] = f"{type(exc).__name__}: {exc}"
            print(f"  {key:26s} FAILED  {type(exc).__name__}")
            continue
        cache[pair] = url
        resolved[key] = url
        print(f"  {key:26s} {url}")

    print(f"\nresolved {len(resolved)}/{len(TARGETS)}")

    if failures:
        print("\nunresolved — deploy the app, or paste the URL from `modal deploy`:")
        for key, reason in failures.items():
            app_name, class_name = TARGETS[key]
            print(f"  {key}: {app_name}/{class_name} — {reason}")

    if args.print_only:
        print(json.dumps(resolved, indent=2))
        return 0

    # Merge rather than overwrite: a URL pasted by hand for an app this lookup
    # cannot reach must survive a later partial run.
    existing = {}
    if OUTPUT.exists():
        existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
    existing.update(resolved)
    OUTPUT.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"\nwrote {OUTPUT} ({len(existing)} entries)")
    return 0 if resolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
