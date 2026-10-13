"""Explicit Modal workspace discovery, verification and safe backend switching.

Run with the Python installation containing Modal and httpx. No API secrets are
written to manifests. Changing CLI profiles does not change backend endpoints.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import wave

BACKEND = Path(__file__).resolve().parents[1]
PROFILES = ("visakanbaskaran", "krishnavaranan1", "krishnavaranan", "varananrp")
SPECS = {
    "MODAL_WHISPER_URL": ("voicelearn-whisper-stt", "WhisperSTT", "transcribe"),
    "MODAL_INDIC_STT_URL": ("voicelearn-tamil-asr-qwen3", "TamilASRQwen3", "transcribe"),
    "MODAL_SINHALA_ASR_URL": ("voicelearn-sinhala-whisper-asr-stage2", "SinhalaWhisperASR", "transcribe"),
    "MODAL_BASE_GEMMA_URL": ("voicelearn-document-gemma", "BaseGemmaAnswer", "generate"),
    "MODAL_RAG_GENERATOR_URL": ("voicelearn-rag-generator-v2", "RAGGenerator", "generate"),
    "MODAL_TRANSCRIPT_CORRECTOR_URL": ("voicelearn-rag-generator-v2", "RAGGenerator", "correct_transcript"),
    "MODAL_LOCALIZER_URL": ("voicelearn-localizer", "Localizer", "localize"),
    "MODAL_ENGLISH_KOKORO_TTS_URL": ("voicelearn-english-kokoro-tts", "EnglishKokoroTTS", "synthesize"),
    "MODAL_INDIC_PARLER_MIXED_TTS_URL": ("voicelearn-indic-parler-mixed-tts", "IndicParlerMixedTTS", "synthesize"),
    "MODAL_SINHALA_VITS_TTS_URL": ("voicelearn-sinhala-vits-tts", "SinhalaVITSTTS", "synthesize"),
    "MODAL_BGE_EMBED_URL": ("voicelearn-bge-retrieval", "BGEEmbedder", "embed"),
    "MODAL_BGE_RERANK_URL": ("voicelearn-bge-retrieval", "BGEReranker", "rerank"),
}
DEPLOY_FILES = (
    "whisper_stt.py", "tamil_asr_qwen3.py", "sinhala_whisper_asr.py",
    "gemma_answer_generator.py", "rag_generator.py", "localizer.py",
    "english_kokoro_tts.py", "indic_parler_mixed_tts.py", "sinhala_vits_tts.py",
    "bge_retrieval.py",
)
MANIFEST_DIR = BACKEND / "modal_workspaces"
STATE_DIR = BACKEND / ".workspace-runtime"


def cli(profile, *args):
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "modal", *args,
                           "--profile", profile, "--env", "main"], cwd=BACKEND.parent,
                          capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / (profile + "-last-cli-error.log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        raise RuntimeError((result.stdout + result.stderr)[-3500:])
    return result.stdout


def source_digest():
    digest = hashlib.sha256()
    for name in DEPLOY_FILES:
        digest.update(name.encode())
        digest.update((BACKEND / "modal_endpoints" / name).read_bytes())
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def discover(profile):
    # Each invocation runs in its own process, preventing shared SDK profile state.
    os.environ["MODAL_PROFILE"] = profile
    import modal
    endpoints = {}
    errors = {}
    for key, (app, cls, method) in SPECS.items():
        try:
            obj = modal.Cls.from_name(app, cls, environment_name="main")()
            endpoints[key] = getattr(obj, method).get_web_url()
        except Exception as exc:
            errors[key] = type(exc).__name__ + ": " + str(exc)[:200]
    value = {"workspace": profile, "environment": "main", "endpoints": endpoints,
             "discovery_errors": errors}
    write_json(MANIFEST_DIR / (profile + ".json"), value)
    print(json.dumps({"workspace": profile, "resolved": len(endpoints), "errors": errors}))
    return value


def deploy(profile):
    for name in DEPLOY_FILES:
        print(f"[{profile}] deploying {name}", flush=True)
        log = cli(profile, "deploy", str(BACKEND / "modal_endpoints" / name))
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"{profile}-{name}.log").write_text(log, encoding="utf-8")
    manifest = discover(profile)
    manifest["deployed_source_sha256"] = source_digest()
    write_json(MANIFEST_DIR / (profile + ".json"), manifest)


def verify(profile, resume=False):
    import httpx
    path = MANIFEST_DIR / (profile + ".json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    urls = manifest["endpoints"]
    checks = {}
    audio = {}
    verified_source = source_digest()
    report_path = STATE_DIR / (profile + "-verification.json")
    fingerprint = hashlib.sha256(json.dumps(urls, sort_keys=True).encode()).hexdigest()
    if resume and report_path.exists():
        previous = json.loads(report_path.read_text(encoding="utf-8"))
        if previous.get("source_sha256") == verified_source and previous.get("endpoints_sha256") == fingerprint:
            checks = {key: value for key, value in previous["checks"].items() if value["ok"]}
    fixture_dir = STATE_DIR / "fixtures" / profile

    def checkpoint():
        write_json(report_path, {"workspace": profile, "checked_at": time.time(),
                   "source_sha256": verified_source, "endpoints_sha256": fingerprint,
                   "checks": checks, "ready": False})

    def request(name, key, payload=None, files=None, validate=None):
        if checks.get(name, {}).get("ok"):
            if name.startswith("tts_"):
                fixture = fixture_dir / (name + ".wav")
                if fixture.exists():
                    return fixture.read_bytes()
            else:
                return None
        start = time.monotonic()
        try:
            with httpx.Client(timeout=600, follow_redirects=True) as client:
                response = client.post(urls[key], json=payload) if files is None else client.post(urls[key], files=files)
            response.raise_for_status()
            data = response.json() if "json" in response.headers.get("content-type", "") else response.content
            if validate:
                validate(data)
            if name.startswith("tts_") and isinstance(data, bytes):
                fixture_dir.mkdir(parents=True, exist_ok=True)
                (fixture_dir / (name + ".wav")).write_bytes(data)
            checks[name] = {"ok": True, "seconds": round(time.monotonic() - start, 2)}
            return data
        except Exception as exc:
            checks[name] = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:220]}
        finally:
            checkpoint()
            print(json.dumps({"workspace": profile, "check": name, "result": checks[name]}), flush=True)

    def text_field(field):
        def check(data):
            if not isinstance(data, dict) or not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"Missing nonempty {field}")
        return check

    def wav_check(data):
        if not isinstance(data, bytes):
            raise ValueError("Expected audio bytes")
        with wave.open(io.BytesIO(data)) as wav:
            if wav.getnframes() == 0:
                raise ValueError("Empty WAV")

    # Short bounded fixtures exercise real generation; no user documents are altered.
    request("base_rag", "MODAL_BASE_GEMMA_URL", {
        "query": "What do dogs need?", "context": ["Dogs need daily exercise and fresh water."],
        "language": "english", "route": "document_rag_base",
    }, validate=text_field("answer"))
    request("rag_v2", "MODAL_RAG_GENERATOR_URL", {"query": "Summarize in one sentence.", "context": ["Dogs need daily exercise and fresh water."], "language": "english"}, validate=text_field("answer"))
    request("transcript_correction", "MODAL_TRANSCRIPT_CORRECTOR_URL", {"transcript": "dogs need water", "language": "english", "mode": "correct"}, validate=text_field("corrected_transcript"))
    for language, text, key in [("english", "Dogs need fresh water.", "MODAL_ENGLISH_KOKORO_TTS_URL"),
                                ("tamil", "நாய்களுக்கு தண்ணீர் தேவை.", "MODAL_INDIC_PARLER_MIXED_TTS_URL"),
                                ("sinhala", "බල්ලන්ට ජලය අවශ්‍යයි.", "MODAL_SINHALA_VITS_TTS_URL")]:
        payload = {"text": text, "language": language}
        data = request("tts_" + language, key, payload, validate=wav_check)
        if data:
            audio[language] = data
        if language != "english":
            request("localize_" + language, "MODAL_LOCALIZER_URL", {"text": "Dogs need fresh water.", "language": language}, validate=text_field("localized_text"))
    for language, key in [("english", "MODAL_WHISPER_URL"), ("tamil", "MODAL_INDIC_STT_URL"), ("sinhala", "MODAL_SINHALA_ASR_URL")]:
        if language in audio:
            request("asr_" + language, key, files={"audio_file": ("fixture.wav", audio[language], "audio/wav")}, validate=text_field("text" if language == "sinhala" else "transcript"))
        else:
            checks["asr_" + language] = {"ok": False, "error": "TTS fixture unavailable"}

    def embeddings(data):
        if len(data.get("embeddings", [])) != 1 or len(data["embeddings"][0]) != 1024:
            raise ValueError("Expected one 1024-dimensional BGE embedding")
    request("embedding", "MODAL_BGE_EMBED_URL", {"texts": ["Dogs need water."], "normalize": True}, validate=embeddings)
    def reranked(data):
        if not data.get("ranked"):
            raise ValueError("Missing rerank results")
    request("reranker", "MODAL_BGE_RERANK_URL", {"query": "What do dogs need?", "candidates": [{"text": "Dogs need fresh water."}, {"text": "The moon orbits Earth."}], "top_k": 1}, validate=reranked)
    report = {"workspace": profile, "checked_at": time.time(), "source_sha256": verified_source,
              "endpoints_sha256": hashlib.sha256(json.dumps(urls, sort_keys=True).encode()).hexdigest(),
              "checks": checks, "ready": source_digest() == verified_source and len(checks) == 13 and all(x["ok"] for x in checks.values())}
    write_json(report_path, report)
    print(json.dumps({"workspace": profile, "ready": report["ready"]}))
    return report


def update_env(content, values):
    lines = content.splitlines()
    remaining = dict(values)
    result = []
    for line in lines:
        match = re.match(r"\s*([A-Z][A-Z0-9_]*)\s*=", line)
        if match and match[1] in values:
            key = match[1]
            # Eliminate duplicate assignments while preserving unrelated settings.
            if key in remaining:
                result.append(f"{key}={remaining.pop(key)}")
        else:
            result.append(line)
    result.extend(f"{key}={value}" for key, value in remaining.items())
    return "\n".join(result) + "\n"


def switch(profile, env_file=None):
    manifest = json.loads((MANIFEST_DIR / (profile + ".json")).read_text(encoding="utf-8"))
    report = json.loads((STATE_DIR / (profile + "-verification.json")).read_text(encoding="utf-8"))
    if not report["ready"] or report["source_sha256"] != source_digest():
        raise RuntimeError("Workspace has not passed verification for the current model code")
    digest = hashlib.sha256(json.dumps(manifest["endpoints"], sort_keys=True).encode()).hexdigest()
    if report["endpoints_sha256"] != digest or len(manifest["endpoints"]) != len(SPECS):
        raise RuntimeError("Endpoint manifest changed; verify again")
    env = Path(env_file) if env_file is not None else BACKEND / ".env"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    original = env.read_text(encoding="utf-8")
    backup = STATE_DIR / f"env-before-{profile}-{time.time_ns()}.bak"
    backup.write_text(original, encoding="utf-8")
    values = {**manifest["endpoints"], "MODAL_WORKSPACE": profile,
              "MODAL_TOKEN_ID": "", "MODAL_TOKEN_SECRET": ""}
    # These verified functions are public; CLI credentials must not be sent.
    temporary = env.with_suffix(".env.tmp")
    temporary.write_text(update_env(original, values), encoding="utf-8")
    temporary.replace(env)
    print(f"Selected {profile}. Restart the backend to apply. Backup: {backup.name}")


def main():
    global STATE_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["discover", "deploy", "verify", "switch"])
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("--resume", action="store_true", help="Retry failed verification checks for unchanged source and endpoints")
    parser.add_argument("--env-file", type=Path, help="Explicit backend env path for server switching")
    parser.add_argument("--state-dir", type=Path, help="Persistent verification and private backup directory")
    args = parser.parse_args()
    if args.state_dir is not None:
        STATE_DIR = args.state_dir
    if args.command == "verify":
        if not verify(args.profile, resume=args.resume)["ready"]:
            raise SystemExit(1)
    elif args.command == "switch":
        switch(args.profile, args.env_file)
    else:
        {"discover": discover, "deploy": deploy, "switch": switch}[args.command](args.profile)


if __name__ == "__main__":
    main()
