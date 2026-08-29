"""Cloud-only Hugging Face migration for VoiceLearn model volumes.

No model bytes pass through the developer workstation. Existing private Hub
repositories are verified before ``prefetch_visakan`` runs against Visakan.
"""

from __future__ import annotations

import os
from pathlib import Path

import modal


app = modal.App("voicelearn-hf-cloud-migration")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("huggingface_hub[hf_xet]>=0.30,<2")
    .env({"HF_HUB_DISABLE_TELEMETRY": "1"})
)
hf_secret = modal.Secret.from_name("huggingface-secret")
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)
bge_volume = modal.Volume.from_name("voicelearn-bge-models", create_if_missing=True)


@app.function(
    image=image,
    cpu=1,
    memory=1024,
    timeout=10 * 60,
    secrets=[hf_secret],
)
def inspect_existing_repos() -> dict[str, object]:
    """Inspect private repo contents and validate required production files."""
    import json

    from huggingface_hub import HfApi

    token = os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    requirements = {
        "varanankb/VoiceLearn-Gemma-V2-Adapter": {
            "adapter_config.json": 1,
            "adapter_model.safetensors": 262_373_216,
            "tokenizer.json": 1,
            "tokenizer_config.json": 1,
        },
        "varanankb/VoiceLearn-Sinhala-ASR-Stage2": {
            "config.json": 1,
            "generation_config.json": 1,
            "model.safetensors": 966_995_080,
            "processor_config.json": 1,
            "tokenizer.json": 1,
            "tokenizer_config.json": 1,
        },
    }
    result: dict[str, object] = {}
    for repo_id, required in requirements.items():
        info = api.model_info(repo_id=repo_id, files_metadata=True)
        files = {
            sibling.rfilename: int(sibling.size or 0)
            for sibling in (info.siblings or [])
        }
        missing = [filename for filename in required if filename not in files]
        mismatched = {
            filename: {"expected": minimum, "actual": files.get(filename, 0)}
            for filename, minimum in required.items()
            if filename in files and files[filename] < minimum
        }
        result[repo_id] = {
            "private": bool(info.private),
            "revision": info.sha,
            "files": files,
            "missing": missing,
            "mismatched": mismatched,
            "complete": not missing and not mismatched,
        }
    print(json.dumps(result, sort_keys=True))
    return result


@app.function(
    image=image,
    cpu=2,
    memory=4096,
    timeout=3 * 60 * 60,
    secrets=[hf_secret],
    volumes={"/models": model_volume, "/bge_models": bge_volume},
)
def prefetch_visakan() -> dict[str, object]:
    """Download all production model files directly from HF into Visakan volumes."""
    import json

    from huggingface_hub import snapshot_download
    from urllib.request import urlretrieve

    token = os.environ["HF_TOKEN"]
    completed: list[str] = []
    errors: dict[str, str] = {}

    def fetch(
        repo_id: str,
        *,
        cache_dir: str | None = None,
        local_dir: str | None = None,
        allow_patterns: list[str] | None = None,
        volume: modal.Volume = model_volume,
    ) -> None:
        try:
            snapshot_download(
                repo_id=repo_id,
                repo_type="model",
                cache_dir=cache_dir,
                local_dir=local_dir,
                allow_patterns=allow_patterns,
                token=token,
                max_workers=4,
            )
            volume.commit()
            completed.append(repo_id)
        except Exception as exc:
            errors[repo_id] = f"{type(exc).__name__}: {exc}"

    # Existing private fine-tuned repos keep the exact paths expected by apps.
    fetch(
        "varanankb/VoiceLearn-Gemma-V2-Adapter",
        local_dir="/models/gemma/adapters/v2",
    )
    fetch(
        "varanankb/VoiceLearn-Sinhala-ASR-Stage2",
        local_dir="/models/sinhala_asr/stage2_final",
    )

    # Gated base model and public production models.
    fetch("google/gemma-4-12B-it", local_dir="/models/gemma/base")
    fetch(
        "dialoglk/SinhalaVITS-TTS-M2",
        local_dir="/models/sinhala-vits-m2",
        allow_patterns=["Roshan_270000.pth", "Roshan_config.json"],
    )
    fetch("Systran/faster-whisper-large-v3", cache_dir="/models")
    # The gated multilingual IndicConformer is not needed: the legacy
    # voicelearn-indic-stt app name is backed by the compatible Qwen3 Tamil ASR.
    # Sinhala uses the dedicated VITS deployment; facebook/mms-tts-sin does not
    # exist as a per-language Hub repository.
    for language in ("eng", "tam"):
        fetch(f"facebook/mms-tts-{language}", cache_dir="/models")
    fetch("Qwen/Qwen2.5-7B-Instruct", cache_dir="/models")
    fetch("osmapi/tamil-asr-qwen3", cache_dir="/models/tamil-asr-qwen3")
    fetch("hexgrad/Kokoro-82M", cache_dir="/models/huggingface")
    fetch("ai4bharat/IndicF5", cache_dir="/models")
    fetch("ai4bharat/indic-parler-tts", cache_dir="/models/indic-parler-tts")
    fetch("BAAI/bge-m3", cache_dir="/bge_models", volume=bge_volume)
    fetch("BAAI/bge-reranker-v2-m3", cache_dir="/bge_models", volume=bge_volume)

    reference_path = Path("/models/indicf5/tamil_ref.wav")
    if not reference_path.exists():
        try:
            reference_path.parent.mkdir(parents=True, exist_ok=True)
            urlretrieve(
                "https://github.com/AI4Bharat/IndicF5/raw/refs/heads/main/"
                "prompts/PAN_F_HAPPY_00001.wav",
                reference_path,
            )
            model_volume.commit()
            completed.append("AI4Bharat/IndicF5 Tamil reference audio")
        except Exception as exc:
            errors["AI4Bharat/IndicF5 Tamil reference audio"] = (
                f"{type(exc).__name__}: {exc}"
            )

    required_files = {
        "gemma_base": "/models/gemma/base/model.safetensors",
        "gemma_adapter": "/models/gemma/adapters/v2/adapter_model.safetensors",
        "sinhala_stage2": "/models/sinhala_asr/stage2_final/model.safetensors",
        "sinhala_tts": "/models/sinhala-vits-m2/Roshan_270000.pth",
    }
    verified = {
        name: Path(path).stat().st_size if Path(path).is_file() else 0
        for name, path in required_files.items()
    }
    result = {
        "completed": completed,
        "errors": errors,
        "verified_bytes": verified,
    }
    print(json.dumps(result, sort_keys=True))
    return result
