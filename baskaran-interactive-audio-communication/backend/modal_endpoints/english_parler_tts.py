"""Modal endpoint: Parler-TTS Mini v1 English text-to-speech.

Deploy:
    modal deploy backend/modal_endpoints/english_parler_tts.py

Accepts JSON:
    { "text": str, "description": str (optional) }

Returns: audio/wav bytes (audio/wav)

The description controls the speaking style (gender, speed, tone, etc.).
If omitted, a default educational voice description is used.

This endpoint ONLY handles English. Tamil must use tamil_parler_tts.py.
"""

import io
import re
import time
from typing import List

import modal
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

# ── Modal infra ────────────────────────────────────────────────────────────────

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libsndfile1", "ffmpeg")
    .pip_install(
        # Pin torch explicitly before parler-tts to avoid CPU-only wheels
        "torch>=2.1.0",
        "parler-tts",
        "transformers>=4.40.0",
        "soundfile>=0.12.1",
        "scipy>=1.11.4",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
        "huggingface_hub>=0.24.0",
    )
)

# Stable app name — its deployed web endpoint is stored in MODAL_ENGLISH_TTS_URL.
app = modal.App("voicelearn-english-parler-tts", image=image)

# Reuse the shared model volume; English model cached under a separate subdirectory
# so it never conflicts with Tamil IndicF5 weights.
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

MODEL_ID = "parler-tts/parler-tts-mini-v1"
CACHE_DIR = "/models"
MODEL_CACHE_PATH = f"{CACHE_DIR}/parler-tts-mini-v1"

# ── Default voice description ─────────────────────────────────────────────────
# Centralised here — callers may override per-request.
# Parler-TTS interprets this natural-language description to control
# the speaker's gender, pace, tone, recording quality, etc.
DEFAULT_DESCRIPTION = (
    "A clear, warm English speaker with a calm educational tone, "
    "moderate speaking speed, natural pauses, confident delivery, "
    "and clean studio-quality audio."
)

# ── Text chunking ─────────────────────────────────────────────────────────────
# Parler-TTS Mini handles ~200-300 chars well per call; very long inputs cause
# degraded quality or OOM.  We split at sentence boundaries.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
MAX_CHUNK_CHARS = 300


# ── Pydantic request schema ────────────────────────────────────────────────────

class EnglishTTSRequest(BaseModel):
    text: str
    description: str = Field(default="", description="Optional speaking-style description")


# ── Text splitter ──────────────────────────────────────────────────────────────

def _split_english_text(text: str) -> List[str]:
    """Split text at sentence boundaries without cutting mid-word."""
    chunks: List[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT_RE.split(text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= MAX_CHUNK_CHARS:
            current = f"{current} {sentence}".strip()
            continue
        if current:
            chunks.append(current)
        if len(sentence) <= MAX_CHUNK_CHARS:
            current = sentence
            continue
        # Sentence itself is too long — word-level split
        current = ""
        for word in sentence.split():
            if len(current) + len(word) + 1 <= MAX_CHUNK_CHARS:
                current = f"{current} {word}".strip()
            else:
                if current:
                    chunks.append(current)
                current = word
    if current:
        chunks.append(current)
    return chunks or [text[:MAX_CHUNK_CHARS]]


# ── Modal class ────────────────────────────────────────────────────────────────

@app.cls(
    # T4 (16 GB VRAM) is cost-efficient for Parler-TTS Mini v1 (~880 M params).
    # The model comfortably fits in T4 VRAM; A10G would be overkill.
    gpu="T4",
    volumes={CACHE_DIR: model_volume},
    scaledown_window=300,      # keep container warm for 5 min after last request
    memory=8192,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class EnglishParlerTTS:
    """Parler-TTS Mini v1 English synthesis running on Modal T4."""

    @modal.enter()
    def load_model(self):
        import os
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        started = time.perf_counter()
        token = os.environ.get("HF_TOKEN")

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[EnglishParlerTTS] Loading {MODEL_ID} on {self._device} ...")

        # Weights are cached in the Modal Volume under MODEL_CACHE_PATH so
        # subsequent cold-starts skip the HuggingFace download entirely.
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(
            MODEL_ID,
            cache_dir=MODEL_CACHE_PATH,
            token=token,
        ).to(self._device)
        self._model.eval()

        self._tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            cache_dir=MODEL_CACHE_PATH,
            token=token,
        )

        # Persist any newly downloaded weights to the volume immediately
        # so they survive container restarts.
        model_volume.commit()

        elapsed = time.perf_counter() - started
        print(
            f"[EnglishParlerTTS] Ready on {self._device} in {elapsed:.2f}s "
            f"(model: {MODEL_ID})"
        )

    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: EnglishTTSRequest) -> Response:
        import traceback
        import numpy as np
        import soundfile as sf
        import torch

        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        # Use the caller's description or fall back to the educational default.
        description = (req.description or "").strip() or DEFAULT_DESCRIPTION

        started = time.perf_counter()
        print(
            f"[EnglishParlerTTS] Synthesizing {len(text)} chars | "
            f"description='{description[:60]}…'"
        )

        try:
            chunks = _split_english_text(text)
            waveforms: List[np.ndarray] = []

            for chunk in chunks:
                print(f"[EnglishParlerTTS] chunk ({len(chunk)} chars): {chunk[:60]}")
                # Tokenize description + text input
                desc_inputs = self._tokenizer(
                    description,
                    return_tensors="pt",
                ).to(self._device)

                text_inputs = self._tokenizer(
                    chunk,
                    return_tensors="pt",
                ).to(self._device)

                with torch.inference_mode():
                    generation = self._model.generate(
                        input_ids=desc_inputs.input_ids,
                        attention_mask=desc_inputs.attention_mask,
                        prompt_input_ids=text_inputs.input_ids,
                        prompt_attention_mask=text_inputs.attention_mask,
                    )

                # generation is (1, samples) on GPU — move to CPU numpy
                audio = generation.cpu().numpy().squeeze()
                audio = audio.astype(np.float32)
                waveforms.append(audio)

            if not waveforms:
                raise HTTPException(
                    status_code=500,
                    detail="Parler-TTS returned no audio — text splitting produced 0 chunks.",
                )

            # Concatenate chunks with a short silence gap between sentences
            sample_rate = self._model.config.sampling_rate
            silence = np.zeros(int(sample_rate * 0.15), dtype=np.float32)
            combined = waveforms[0]
            for waveform in waveforms[1:]:
                combined = np.concatenate((combined, silence, waveform))

            # Normalise to prevent clipping
            peak = np.abs(combined).max()
            if peak > 0:
                combined = combined / peak * 0.95

            # Encode as WAV
            buffer = io.BytesIO()
            sf.write(buffer, combined, sample_rate, format="WAV", subtype="PCM_16")

            elapsed = time.perf_counter() - started
            print(
                f"[TIMING] english_parler_tts_generation: {elapsed:.3f}s | "
                f"{len(text)} chars | {len(chunks)} chunk(s)"
            )

            return Response(content=buffer.getvalue(), media_type="audio/wav")

        except HTTPException:
            raise
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[EnglishParlerTTS] SYNTHESIS ERROR: {exc}\n{tb}")
            raise HTTPException(
                status_code=500,
                detail=f"Parler-TTS synthesis failed: {type(exc).__name__}: {exc}",
            )
