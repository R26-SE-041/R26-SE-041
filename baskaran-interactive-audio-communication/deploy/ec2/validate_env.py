"""Fail closed before public deployment, without printing credential values."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


def read_env(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        if key in values:
            raise ValueError(f"Duplicate environment key: {key}")
        values[key] = value
    return values


def validate(backend, gateway, proxy):
    required = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
                "OPENCLAW_GATEWAY_TOKEN", "ACTIONS_BRIDGE_SECRET"]
    for key in required:
        value = backend.get(key, "")
        if not value or any(word in value.upper() for word in ["REPLACE", "GENERATE_", "PLACEHOLDER", "YOUR-"]):
            raise ValueError(f"Configure {key} before deployment")
    if not backend["SUPABASE_URL"].startswith("https://"):
        raise ValueError("Supabase URL must use HTTPS")
    for key in ["OPENCLAW_GATEWAY_TOKEN", "ACTIONS_BRIDGE_SECRET"]:
        if len(backend[key]) < 32 or gateway.get(key) != backend[key]:
            raise ValueError(f"Use matching strong {key} in both environment files")
    if not gateway.get("GEMINI_API_KEY") or "REPLACE" in gateway["GEMINI_API_KEY"]:
        raise ValueError("Configure GEMINI_API_KEY")
    if backend.get("ACTIONS_PROVIDER") != "openclaw_mcp" or backend.get("ACTIONS_ENABLED", "").lower() != "true":
        raise ValueError("Enable the configured OpenClaw action provider")
    origins = json.loads(backend.get("ALLOWED_ORIGINS", "[]"))
    if not origins or any(urlparse(x).scheme != "https" or '*' in x for x in origins):
        raise ValueError("Configure explicit HTTPS frontend CORS origins")
    for key in ["MODAL_WHISPER_URL", "MODAL_INDIC_STT_URL", "MODAL_SINHALA_ASR_URL",
                "MODAL_BASE_GEMMA_URL", "MODAL_RAG_GENERATOR_URL", "MODAL_TRANSCRIPT_CORRECTOR_URL",
                "MODAL_LOCALIZER_URL", "MODAL_ENGLISH_KOKORO_TTS_URL", "MODAL_INDIC_PARLER_MIXED_TTS_URL",
                "MODAL_SINHALA_VITS_TTS_URL", "MODAL_BGE_EMBED_URL", "MODAL_BGE_RERANK_URL"]:
        if urlparse(backend.get(key, "")).scheme != "https":
            raise ValueError(f"Configure verified HTTPS endpoint: {key}")
    domain = proxy.get("API_DOMAIN", "")
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", domain) or '.' not in domain or domain.endswith(".example"):
        raise ValueError("Configure a real backend DNS domain")


if __name__ == "__main__":
    try:
        validate(*(read_env(path) for path in sys.argv[1:]))
    except (ValueError, OSError, TypeError) as error:
        print(f"Deployment preflight failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Deployment configuration passed; credentials were not printed.")
