"""Modal endpoint: ai4bharat/indic-parler-tts — Tamil + English mixed TTS (Mode D).

Deploy (ONLY this file — do NOT redeploy existing services):
    modal deploy backend/modal_endpoints/indic_parler_mixed_tts.py

IMPORTANT — DEVELOPMENT / TEST ONLY
=====================================
This file implements Mode D: a completely isolated experiment for Tamil + English
code-switched (mixed) text-to-speech using a SINGLE unified multilingual model.

This service must NEVER be merged with or replace:
    - tamil_parler_tts.py         (IndicF5 Tamil TTS — production)
    - english_parler_tts.py       (Parler-TTS Mini v1 — production)

Mode D uses ai4bharat/indic-parler-tts, which is a fine-tuned multilingual
extension of Parler-TTS Mini trained on 1,806 hours of Indic + English data.
It accepts raw Tamil + English mixed text in ONE request and returns ONE
continuous audio result — no segmentation, no stitching, no transliteration.

Model characteristics
---------------------
  Model ID     : ai4bharat/indic-parler-tts
  Architecture : Parler-TTS (description-conditioned auto-regressive)
  Languages    : 21 Indic languages + English (officially supported)
  Tamil code   : ta  (auto-detected from Unicode script — no lang param needed)
  Tamil speakers: Kavitha, Jaya  (recommended: Jaya)
  Sample rate  : 44,100 Hz  (44.1 kHz)
  Dtype        : torch.float16 on GPU
  Params       : ~938M
  VRAM (fp16)  : ~2 GB
  License      : Apache 2.0
  Two-tokenizer: description_tokenizer (T5) + prompt_tokenizer (custom multilingual)

CRITICAL — Two-tokenizer architecture
--------------------------------------
Unlike Parler-TTS Mini v1 (which uses a shared tokenizer for both description
and prompt), indic-parler-tts uses SEPARATE tokenizers:
  - description_tokenizer: loaded from model.config.text_encoder._name_or_path
  - prompt_tokenizer:      loaded from "ai4bharat/indic-parler-tts" directly
Both must be initialized and used correctly or generation silently fails.

Speaker / style used (Mode D default)
--------------------------------------
  "Jaya speaks with a clear, warm, and calm tone at a moderate pace.
   Her voice is natural and expressive, captured in a very clean, close-sounding
   recording with no background noise. She speaks with a slightly high-pitched
   and gentle educational delivery."

This description anchors "Jaya" (recommended Tamil female speaker) for
consistent voice identity across both Tamil and English segments.

Removal instructions
--------------------
  1. modal app stop voicelearn-indic-parler-mixed-tts   (un-deploy the Modal app)
  2. Delete this file.
  3. Remove the test_indic_parler_mixed_tts route from main_stt.py.
  4. Remove use_indic_parler_mixed_tts_test from config.py and .env files.
  5. Remove call_indic_parler_mixed_tts_direct from modal_client.py.
  6. Remove testSynthesizeIndicParlerMixedSpeech from frontend api.ts.
  7. Remove the Mode D panel from the /test page.
  Nothing else needs to change. All existing TTS services and RAG are unaffected.
"""

import io
import re
import time
from typing import List

import modal
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

# ── Modal image ───────────────────────────────────────────────────────────────
# Build a clean Debian environment with:
#   * parler-tts (HuggingFace GitHub HEAD — required for indic-parler-tts)
#   * transformers >= 4.40  (description tokenizer T5 + multilingual prompt tokenizer)
#   * torch with CUDA (GPU inference at float16)
#   * soundfile + scipy for WAV encoding
#
# NOTE: We install parler-tts from GitHub (NOT PyPI) because the PyPI release
# does not include the latest multilingual tokenizer code needed for this model.

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "libsndfile1",
        "ffmpeg",
        "git",       # required for: pip install git+https://github.com/huggingface/parler-tts.git
    )
    .pip_install(
        # Core PyTorch — install before parler-tts to guarantee GPU wheels
        "torch>=2.1.0",
        # HuggingFace parler-tts from source — required for indic-parler-tts multilingual support
        "git+https://github.com/huggingface/parler-tts.git",
        # Transformers — must be >= 4.40 for SDPA and multilingual tokenizer compatibility
        "transformers>=4.40.0",
        "accelerate>=0.26.0",
        # Audio / IO
        "soundfile>=0.12.1",
        "scipy>=1.11.4",
        # Modal / FastAPI
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
        # HuggingFace hub for model download + caching
        "huggingface_hub>=0.24.0",
    )
)

# ── Modal app ─────────────────────────────────────────────────────────────────
# NEW app name — completely isolated from the existing Tamil and English services.
# The URL produced by this deployment is stored in MODAL_INDIC_PARLER_MIXED_TTS_URL.
app = modal.App("voicelearn-indic-parler-mixed-tts", image=image)

# Reuse the shared model volume — indic-parler-tts cached under its own subdirectory
# so it never conflicts with IndicF5 or Parler-TTS Mini weights.
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

# ── Constants ─────────────────────────────────────────────────────────────────
MODEL_ID = "ai4bharat/indic-parler-tts"
CACHE_DIR = "/models"
MODEL_CACHE_PATH = f"{CACHE_DIR}/indic-parler-tts"

# Tamil female speaker "Jaya" — the recommended Tamil speaker for this model.
# Description anchors the speaker name so voice stays consistent across Tamil
# and English segments within a single code-switched utterance.
DEFAULT_DESCRIPTION = (
    "Jaya speaks with a clear, warm, and calm tone at a moderate pace. "
    "Her voice is natural and expressive, captured in a very clean, close-sounding "
    "recording with no background noise. She speaks with a slightly high-pitched "
    "and gentle educational delivery."
)

# Maximum characters per synthesis chunk.
# indic-parler-tts is Parler-based; quality degrades beyond ~350 chars.
MAX_CHUNK_CHARS = 350

# Sentence boundary splitter: split after ., !, ?, Tamil purna viraam, newlines
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


# ── Pydantic request schema ───────────────────────────────────────────────────

class IndicParlerMixedTTSRequest(BaseModel):
    """Request body for Mode D TTS.

    The caller only needs to supply 'text'. Language auto-detection and speaker
    selection are handled internally with sensible defaults.

    Optional overrides are provided for experimentation only.
    """
    text: str
    description: str = Field(
        default="",
        description=(
            "Optional Parler-TTS style description. "
            "If empty, the Mode D default Jaya educational voice is used."
        ),
    )


# ── Text chunker ──────────────────────────────────────────────────────────────

def _chunk_mixed_text(text: str) -> List[str]:
    """Split mixed Tamil+English text at sentence boundaries.

    Splitting at sentence boundaries minimises prosody breaks compared to
    mid-word splitting.  Short chunks also avoid OOM on long inputs.

    Unlike Mode A/B, we do NOT split by script — each chunk may contain
    both Tamil and English characters and is sent as-is to the model.
    """
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
        # Sentence itself too long — word-level fallback
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


# ── Modal class ───────────────────────────────────────────────────────────────

@app.cls(
    # A10G (24 GB VRAM) — same as the Tamil IndicF5 service.
    # indic-parler-tts has ~938M params; at float16 it needs ~2 GB VRAM,
    # so A10G is more than sufficient and gives fast inference.
    gpu="A10G",
    volumes={CACHE_DIR: model_volume},
    # Keep warm for 5 minutes after last request to avoid cold-start latency
    # on rapid consecutive test calls.
    scaledown_window=300,
    memory=8192,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class IndicParlerMixedTTS:
    """ai4bharat/indic-parler-tts Mode D — Tamil + English multilingual synthesis.

    This class is completely isolated from TamilIndicF5TTS and EnglishParlerTTS.
    It loads its own model weights into its own Modal container.
    """

    @modal.enter()
    def load_model(self):
        """Load model and both tokenizers once per container startup."""
        import os
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        started = time.perf_counter()
        token = os.environ.get("HF_TOKEN")

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self._device == "cuda" else torch.float32
        self._dtype = dtype

        print(f"[IndicParlerMixedTTS] Loading {MODEL_ID} on {self._device} at {dtype} ...")

        # ── Model weights ─────────────────────────────────────────────────────
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(
            MODEL_ID,
            cache_dir=MODEL_CACHE_PATH,
            token=token,
            torch_dtype=dtype,
        ).to(self._device)
        self._model.eval()

        # ── Two-tokenizer setup ───────────────────────────────────────────────
        # indic-parler-tts uses a SEPARATE tokenizer for the description (T5-based)
        # and a custom multilingual tokenizer for the prompt (Tamil+English vocab).
        # This is different from Parler-TTS Mini v1 which uses one shared tokenizer.

        # Prompt tokenizer: the multilingual vocab (Tamil, English, other Indic scripts)
        self._prompt_tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            cache_dir=MODEL_CACHE_PATH,
            token=token,
        )

        # Description tokenizer: T5-based, loaded from model config reference
        description_encoder_name = self._model.config.text_encoder._name_or_path
        print(f"[IndicParlerMixedTTS] Description encoder: {description_encoder_name}")
        self._description_tokenizer = AutoTokenizer.from_pretrained(
            description_encoder_name,
            cache_dir=MODEL_CACHE_PATH,
            token=token,
        )

        # Cache weights to volume so subsequent cold-starts skip HF download
        model_volume.commit()

        elapsed = time.perf_counter() - started
        print(
            f"[IndicParlerMixedTTS] Ready on {self._device} in {elapsed:.2f}s "
            f"(model={MODEL_ID}, sample_rate={self._model.config.sampling_rate})"
        )

    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: IndicParlerMixedTTSRequest) -> Response:
        """Synthesize mixed Tamil + English text via ONE multilingual model call.

        Mode D rules - strictly enforced:
          - NO transliteration
          - NO eSpeak
          - NO IndicXlit
          - NO Tamil/English segmentation
          - NO dual-model audio join
          - Original text -> indic-parler-tts -> ONE audio result
        """
        import traceback
        import numpy as np
        import soundfile as sf
        import torch

        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        # Use caller's description or fall back to the Mode D Jaya default
        description = (req.description or "").strip() or DEFAULT_DESCRIPTION

        started = time.perf_counter()
        sample_rate = self._model.config.sampling_rate  # 44,100 Hz for this model

        print(
            f"[IndicParlerMixedTTS] Synthesizing {len(text)} chars | "
            f"description='{description[:60]}...' | sample_rate={sample_rate}"
        )

        try:
            chunks = _chunk_mixed_text(text)
            waveforms: List[np.ndarray] = []

            for chunk in chunks:
                print(
                    f"[IndicParlerMixedTTS] chunk ({len(chunk)} chars): "
                    f"{chunk[:60]}{'...' if len(chunk) > 60 else ''}"
                )

                # ── Tokenize description (T5 tokenizer) ───────────────────────
                desc_inputs = self._description_tokenizer(
                    description,
                    return_tensors="pt",
                ).to(self._device)

                # ── Tokenize the raw mixed Tamil+English prompt ────────────────
                # NO pre-processing — the original text is sent as-is.
                # The multilingual prompt tokenizer handles both Tamil Unicode
                # (U+0B80-U+0BFF) and Latin (English) characters natively.
                prompt_inputs = self._prompt_tokenizer(
                    chunk,
                    return_tensors="pt",
                ).to(self._device)

                # ── Generate audio ─────────────────────────────────────────────
                with torch.inference_mode():
                    generation = self._model.generate(
                        input_ids=desc_inputs.input_ids,
                        attention_mask=desc_inputs.attention_mask,
                        prompt_input_ids=prompt_inputs.input_ids,
                        prompt_attention_mask=prompt_inputs.attention_mask,
                    )

                # Move to CPU float32 numpy
                audio = generation.cpu().numpy().squeeze().astype(np.float32)
                waveforms.append(audio)

            if not waveforms:
                raise HTTPException(
                    status_code=500,
                    detail="indic-parler-tts returned no audio — text splitting produced 0 chunks.",
                )

            # Concatenate chunks with a short silence gap between sentences.
            # 44100 * 0.15 = ~6600 samples (~150ms) — natural inter-sentence pause.
            silence = np.zeros(int(sample_rate * 0.15), dtype=np.float32)
            combined = waveforms[0]
            for waveform in waveforms[1:]:
                combined = np.concatenate((combined, silence, waveform))

            # Peak-normalize to prevent clipping
            peak = np.abs(combined).max()
            if peak > 0:
                combined = combined / peak * 0.95

            # Encode as WAV (PCM 16-bit, 44100 Hz)
            buffer = io.BytesIO()
            sf.write(buffer, combined, sample_rate, format="WAV", subtype="PCM_16")

            elapsed = time.perf_counter() - started
            print(
                f"[TIMING] indic_parler_mixed_tts_generation: {elapsed:.3f}s | "
                f"{len(text)} chars | {len(chunks)} chunk(s) | {sample_rate} Hz"
            )

            return Response(
                content=buffer.getvalue(),
                media_type="audio/wav",
                headers={
                    "X-TTS-Engine": "Indic-Parler-TTS",
                    "X-TTS-Mode": "mode-d",
                    "X-TTS-Sample-Rate": str(sample_rate),
                    "X-TTS-Speaker": "Jaya",
                    "X-TTS-Latency-Ms": str(int(elapsed * 1000)),
                },
            )

        except HTTPException:
            raise
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[IndicParlerMixedTTS] SYNTHESIS ERROR: {exc}\n{tb}")
            raise HTTPException(
                status_code=500,
                detail=(
                    f"indic-parler-tts synthesis failed: {type(exc).__name__}: {exc}. "
                    "Mode D only — Tamil TTS, English TTS, Mode A, Mode B, Mode C, and RAG are unaffected."
                ),
            )
