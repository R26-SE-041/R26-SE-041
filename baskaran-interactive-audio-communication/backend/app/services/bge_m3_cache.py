"""Fast, dependency-free preflight checks for the locally provisioned BGE-M3 model."""

from __future__ import annotations

import json
import os
from pathlib import Path


MODEL_ID = "BAAI/bge-m3"
_REQUIRED_FILES = (
    "config.json",
    "modules.json",
    "sentence_bert_config.json",
    "tokenizer.json",
)
_MINIMUM_WEIGHT_BYTES = 100 * 1024 * 1024


def _hub_cache_root() -> Path:
    """Return the Hugging Face hub directory without importing huggingface_hub."""
    configured = os.environ.get("HF_HUB_CACHE")
    if configured:
        return Path(configured)
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _valid_safetensors_file(path: Path) -> bool:
    """Reject truncated/corrupt safetensors files using only their small header."""
    try:
        size = path.stat().st_size
        if size < _MINIMUM_WEIGHT_BYTES:
            return False
        with path.open("rb") as handle:
            header_size = int.from_bytes(handle.read(8), "little")
            if not 2 < header_size < 100 * 1024 * 1024 or header_size + 8 >= size:
                return False
            header = json.loads(handle.read(header_size))
        return isinstance(header, dict) and bool(header)
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _valid_pytorch_file(path: Path) -> bool:
    """Accept a complete PyTorch checkpoint without importing torch.

    BGE-M3 publishes both safetensors and ``pytorch_model.bin`` checkpoints.
    Sentence Transformers can load either format, so rejecting the latter
    makes a valid local cache look unavailable.
    """
    try:
        return path.is_file() and path.stat().st_size >= _MINIMUM_WEIGHT_BYTES
    except OSError:
        return False


def bge_m3_cache_status() -> tuple[bool, str]:
    """Return whether BGE-M3 is complete enough to enter the heavy model loader.

    This deliberately never imports transformers, sentence-transformers, or
    huggingface_hub, and never performs a network request.
    """
    snapshots = _hub_cache_root() / "models--BAAI--bge-m3" / "snapshots"
    if not snapshots.is_dir():
        return False, "no local BGE-M3 snapshot was found"

    for snapshot in snapshots.iterdir():
        if not snapshot.is_dir():
            continue
        if any(not (snapshot / name).is_file() for name in _REQUIRED_FILES):
            continue
        safetensors = tuple(snapshot.glob("*.safetensors"))
        pytorch_weights = tuple(snapshot.glob("pytorch_model*.bin"))
        if (
            any(_valid_safetensors_file(weight) for weight in safetensors)
            or any(_valid_pytorch_file(weight) for weight in pytorch_weights)
        ):
            return True, "ready"

    return False, "model weights are missing, incomplete, or corrupt"
