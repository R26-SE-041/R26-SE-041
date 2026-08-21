"""Final Tamil TTS service using ``ai4bharat/indic-parler-tts``.

The Modal application name and environment key remain stable for the existing
deployment. The production backend sends the selected-language Tamil answer to
this endpoint without experimental segmentation or phonetic preprocessing.

Deploy with:
    modal deploy backend/modal_endpoints/indic_parler_mixed_tts.py

The model uses its separate description and multilingual prompt tokenizers and
returns a single 44.1 kHz WAV response. Tamil and English keep their recommended
Jaya and Mary voices while small ordered batches avoid one expensive sequential
model generation for every language switch.
"""

import io
import os
import re
import time
import unicodedata
from typing import List, Literal, NamedTuple

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
# Keep the established app name and URL key so the deployed service remains stable.
APP_NAME = os.environ.get(
    "VOICELEARN_TTS_APP_NAME", "voicelearn-indic-parler-mixed-tts"
)
GPU_TYPE = os.environ.get("VOICELEARN_TTS_GPU", "A10G")
app = modal.App(APP_NAME, image=image)

# Reuse the shared model volume — indic-parler-tts cached under its own subdirectory
# so it never conflicts with IndicF5 or Parler-TTS Mini weights.
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

# ── Constants ─────────────────────────────────────────────────────────────────
MODEL_ID = "ai4bharat/indic-parler-tts"
CACHE_DIR = "/models"
MODEL_CACHE_PATH = f"{CACHE_DIR}/indic-parler-tts"

# The model-card recommended speakers for Tamil and English.
TAMIL_DESCRIPTION = (
    "Jaya speaks with a slightly low-pitched, quite monotone voice at a slightly "
    "faster-than-average pace in a confined space with very clear audio."
)
ENGLISH_DESCRIPTION = (
    "Mary speaks English with a clear, natural educational voice at a slightly "
    "faster-than-average pace in a confined space with very clear audio."
)

# Short chunks retain clearer pronunciation and more stable mixed-language prosody.
MAX_CHUNK_WORDS = 25
MAX_CHUNK_CHARS = 280
GENERATION_BATCH_SIZE = 1
LANGUAGE_SWITCH_PAUSE_SECONDS = 0.03
CHUNK_PAUSE_SECONDS = 0.12

# Sentence boundary splitter: split after ., !, ?, Tamil purna viraam, newlines
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_LANGUAGE_TOKEN_RE = re.compile(
    r"[\u0B80-\u0BFF]+|[A-Za-z]+(?:[A-Za-z0-9'._+-]*[A-Za-z0-9])?|\d+(?:[.,]\d+)*|[^\u0B80-\u0BFFA-Za-z\d]+"
)


class SpeechSegment(NamedTuple):
    text: str
    language: Literal["tamil", "english"]
    ends_chunk: bool


def _clean_prompt_text(text: str) -> str:
    """Remove visual markup while preserving Tamil and English verbatim."""
    value = unicodedata.normalize("NFC", text or "")
    value = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"https?://\S+|www\.\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*(?:[-+*•●▪◦]\s+|\d+[.)]\s+)", ". ", value)
    value = re.sub(r"[*_~`]+", "", value)
    value = value.translate(str.maketrans({
        "–": ", ", "—": ", ", "…": ". ", "•": ". ",
        "●": ". ", "▪": ". ", "◦": ". ", "|": ", ",
    }))
    value = re.sub(r"\s*\n\s*", ". ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"(?:\.\s*){2,}", ". ", value)
    value = re.sub(r"[:;]\s*\.\s*", ". ", value)
    value = value.strip()
    return re.sub(r"^\.\s*", "", value)


# ── Pydantic request schema ───────────────────────────────────────────────────

class IndicParlerMixedTTSRequest(BaseModel):
    """Request body for final Tamil TTS.

    The caller only needs to supply 'text'. Language auto-detection and speaker
    selection are handled internally with sensible defaults.

    The optional description controls speaking style.
    """
    text: str
    description: str = Field(
        default="",
        description=(
            "Optional Parler-TTS style description. "
            "If empty, Jaya is used for Tamil and Mary for English."
        ),
    )


# ── Text chunker ──────────────────────────────────────────────────────────────

def _chunk_clean_text(text: str) -> List[str]:
    """Split preprocessed Tamil+English text at sentence boundaries.

    Splitting at sentence boundaries minimises prosody breaks compared to
    mid-word splitting.  Short chunks also avoid OOM on long inputs.

    Each returned chunk is passed to the multilingual prompt tokenizer as-is.
    """
    chunks: List[str] = []

    for sentence in _SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        # Keep every sentence/list item independent.  In a multi-item prompt
        # Parler can emit EOS after item one and silently omit the rest.
        if len(sentence) <= MAX_CHUNK_CHARS and len(sentence.split()) <= MAX_CHUNK_WORDS:
            chunks.append(sentence)
            continue
        # Sentence itself too long — word-level fallback
        current = ""
        for word in sentence.split():
            candidate = f"{current} {word}".strip()
            if len(candidate) <= MAX_CHUNK_CHARS and len(candidate.split()) <= MAX_CHUNK_WORDS:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = word
        if current:
            chunks.append(current)

    return chunks or ([text] if text else [])


def _chunk_mixed_text(text: str) -> List[str]:
    """Compatibility wrapper used by local text-only checks."""
    return _chunk_clean_text(_clean_prompt_text(text))


def _split_language_runs(chunk: str) -> List[SpeechSegment]:
    """Route one complete sentence/list item to one consistent speaker.

    Any chunk containing Tamil stays intact on Jaya, including embedded English
    acronyms and phrases. Mary is used only for an English-only sentence/list
    item. This deliberately avoids resetting speaker identity or prosody inside
    a sentence while preserving the original text verbatim.
    """
    value = chunk.strip()
    if not value or not (_TAMIL_RE.search(value) or re.search(r"[A-Za-z\d]", value)):
        return []

    language: Literal["tamil", "english"] = (
        "tamil" if _TAMIL_RE.search(value) or not re.search(r"[A-Za-z]", value)
        else "english"
    )
    return [SpeechSegment(value, language, True)]


def _language_segments(chunks: List[str]) -> List[SpeechSegment]:
    """Split all chunks without merging across a bullet/sentence boundary."""
    return [segment for chunk in chunks for segment in _split_language_runs(chunk)]


def _description_for_language(language: str) -> str:
    return TAMIL_DESCRIPTION if language == "tamil" else ENGLISH_DESCRIPTION


# ── Modal class ───────────────────────────────────────────────────────────────

@app.cls(
    # A10G (24 GB VRAM) — same as the Tamil IndicF5 service.
    # indic-parler-tts has ~938M params; at float16 it needs ~2 GB VRAM,
    # so A10G is more than sufficient and gives fast inference.
    gpu=GPU_TYPE,
    volumes={CACHE_DIR: model_volume},
    # Keep warm for 5 minutes after last request to avoid cold-start latency
    # on rapid consecutive test calls.
    scaledown_window=300,
    memory=8192,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class IndicParlerMixedTTS:
    """Production Tamil synthesis with ai4bharat/indic-parler-tts."""

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
        self._gpu_name = (
            torch.cuda.get_device_name(0) if self._device == "cuda" else "CPU"
        )
        # Keep the complete Parler/DAC path on float16. Although the A10G can
        # execute bfloat16, the generated waveform eventually crosses a NumPy
        # boundary which does not support that scalar type.
        dtype = torch.float16 if self._device == "cuda" else torch.float32
        self._dtype = dtype

        print(f"[IndicParlerMixedTTS] Loading {MODEL_ID} on {self._device} at {dtype} ...")

        # ── Model weights ─────────────────────────────────────────────────────
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(
            MODEL_ID,
            cache_dir=MODEL_CACHE_PATH,
            token=token,
            torch_dtype=dtype,
            attn_implementation="eager",
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
        # Upstream Parler-TTS batch inference requires left-padded token batches.
        self._prompt_tokenizer.padding_side = "left"

        # Description tokenizer: T5-based, loaded from model config reference
        description_encoder_name = self._model.config.text_encoder._name_or_path
        print(f"[IndicParlerMixedTTS] Description encoder: {description_encoder_name}")
        self._description_tokenizer = AutoTokenizer.from_pretrained(
            description_encoder_name,
            cache_dir=MODEL_CACHE_PATH,
            token=token,
        )
        self._description_tokenizer.padding_side = "left"

        # Cache weights to volume so subsequent cold-starts skip HF download
        model_volume.commit()

        elapsed = time.perf_counter() - started
        print(
            f"[IndicParlerMixedTTS] Ready on {self._device} in {elapsed:.2f}s "
            f"(gpu={self._gpu_name}, model={MODEL_ID}, "
            f"sample_rate={self._model.config.sampling_rate})"
        )

    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: IndicParlerMixedTTSRequest) -> Response:
        """Synthesize the complete answer as multilingual text chunks."""
        import traceback
        import numpy as np
        import soundfile as sf
        import torch

        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        description_override = (req.description or "").strip()

        started = time.perf_counter()
        sample_rate = self._model.config.sampling_rate  # 44,100 Hz for this model

        print(
            f"[IndicParlerMixedTTS] Synthesizing {len(text)} chars | "
            f"description={'custom' if description_override else 'auto-by-script'} | "
            f"sample_rate={sample_rate}"
        )

        try:
            preprocess_started = time.perf_counter()
            clean_text = _clean_prompt_text(text)
            preprocess_elapsed = time.perf_counter() - preprocess_started
            print(f"[TTS-LATENCY] preprocess = {preprocess_elapsed:.3f}s")

            chunking_started = time.perf_counter()
            chunks = _chunk_clean_text(clean_text)
            chunking_elapsed = time.perf_counter() - chunking_started
            print(f"[TTS-LATENCY] chunking = {chunking_elapsed:.3f}s")
            print(f"[TTS-LATENCY] chunks = {len(chunks)}")

            segments = _language_segments(chunks)
            if not segments:
                raise HTTPException(
                    status_code=422,
                    detail="'text' contains no speakable Tamil or English content.",
                )

            planned_generate_calls = (
                len(segments) + GENERATION_BATCH_SIZE - 1
            ) // GENERATION_BATCH_SIZE
            print(f"[TTS-LATENCY] language_segments = {len(segments)}")
            tamil_segments = sum(segment.language == "tamil" for segment in segments)
            english_segments = sum(segment.language == "english" for segment in segments)
            speaker_switches = sum(
                previous.language != current.language
                for previous, current in zip(segments, segments[1:])
            )
            print(f"[TTS-LATENCY] tamil_segments = {tamil_segments}")
            print(f"[TTS-LATENCY] english_segments = {english_segments}")
            print(f"[TTS-LATENCY] speaker_switches = {speaker_switches}")
            print(
                f"[TTS-LATENCY] average_segment_chars = "
                f"{sum(len(segment.text) for segment in segments) / len(segments):.1f}"
            )
            print(f"[TTS-LATENCY] generate_calls = {planned_generate_calls}")

            waveforms: List[np.ndarray] = []
            generation_count = 0
            for batch_start in range(0, len(segments), GENERATION_BATCH_SIZE):
                batch = segments[batch_start : batch_start + GENERATION_BATCH_SIZE]
                descriptions = [
                    description_override or _description_for_language(segment.language)
                    for segment in batch
                ]
                prompts = [segment.text for segment in batch]
                desc_inputs = self._description_tokenizer(
                    descriptions,
                    return_tensors="pt",
                    padding=True,
                ).to(self._device)
                prompt_inputs = self._prompt_tokenizer(
                    prompts,
                    return_tensors="pt",
                    padding=True,
                ).to(self._device)

                generation_started = time.perf_counter()
                with torch.inference_mode():
                    generation = self._model.generate(
                        input_ids=desc_inputs.input_ids,
                        attention_mask=desc_inputs.attention_mask,
                        prompt_input_ids=prompt_inputs.input_ids,
                        prompt_attention_mask=prompt_inputs.attention_mask,
                        do_sample=True,
                        return_dict_in_generate=True,
                    )
                generation_elapsed = time.perf_counter() - generation_started
                generation_count += 1
                batch_languages = {segment.language for segment in batch}
                language_label = (
                    next(iter(batch_languages)) if len(batch_languages) == 1 else "mixed"
                )
                print(
                    f"[TTS-LATENCY] generate #{generation_count} "
                    f"language={language_label} chars={sum(len(item.text) for item in batch)} "
                    f"segments={len(batch)} duration={generation_elapsed:.3f}s"
                )

                for index in range(len(batch)):
                    raw_audio_length = generation.audios_length[index]
                    # Depending on the installed parler-tts/Transformers
                    # revision, audios_length contains either scalar tensors
                    # or plain Python integers. Support both return shapes.
                    audio_length = int(
                        raw_audio_length.item()
                        if hasattr(raw_audio_length, "item")
                        else raw_audio_length
                    )
                    # Slice away batch padding before converting to NumPy.
                    audio = (
                        generation.sequences[index, :audio_length]
                        .float()
                        .cpu()
                        .numpy()
                        .reshape(-1)
                        .astype(np.float32)
                    )
                    if audio.size <= 1:
                        raise RuntimeError(
                            f"indic-parler-tts returned invalid audio for segment {batch_start + index + 1}"
                        )
                    waveforms.append(audio)

            if not waveforms:
                raise HTTPException(
                    status_code=500,
                    detail="indic-parler-tts returned no audio — text splitting produced 0 chunks.",
                )

            concat_started = time.perf_counter()
            language_pause = np.zeros(
                int(sample_rate * LANGUAGE_SWITCH_PAUSE_SECONDS), dtype=np.float32
            )
            chunk_pause = np.zeros(int(sample_rate * CHUNK_PAUSE_SECONDS), dtype=np.float32)
            audio_parts: List[np.ndarray] = []
            for index, waveform in enumerate(waveforms):
                audio_parts.append(waveform)
                if index < len(waveforms) - 1:
                    audio_parts.append(chunk_pause if segments[index].ends_chunk else language_pause)
            combined = np.concatenate(audio_parts)
            concat_elapsed = time.perf_counter() - concat_started
            print(f"[TTS-LATENCY] concat = {concat_elapsed:.3f}s")

            normalize_started = time.perf_counter()
            peak = np.abs(combined).max()
            if peak > 0:
                combined = combined / peak * 0.95
            # The model and final WAV are both 44.1 kHz, so no resample is needed.
            normalize_elapsed = time.perf_counter() - normalize_started
            print(f"[TTS-LATENCY] normalize/resample = {normalize_elapsed:.3f}s")

            # Encode as WAV (PCM 16-bit, 44100 Hz)
            buffer = io.BytesIO()
            sf.write(buffer, combined, sample_rate, format="WAV", subtype="PCM_16")

            elapsed = time.perf_counter() - started
            print(f"[TTS-LATENCY] TOTAL = {elapsed:.3f}s")
            print(
                f"[TIMING] indic_parler_mixed_tts_generation: {elapsed:.3f}s | "
                f"{len(text)} chars | {len(chunks)} chunk(s) | "
                f"{generation_count} generation(s) | {sample_rate} Hz"
            )

            return Response(
                content=buffer.getvalue(),
                media_type="audio/wav",
                headers={
                    "X-TTS-Engine": "Indic-Parler-TTS",
                    "X-TTS-Mode": "tamil-production",
                    "X-TTS-Sample-Rate": str(sample_rate),
                    "X-TTS-Speaker": "Jaya/Mary",
                    "X-TTS-Chunks": str(len(chunks)),
                    "X-TTS-Language-Segments": str(len(segments)),
                    "X-TTS-Tamil-Segments": str(tamil_segments),
                    "X-TTS-English-Segments": str(english_segments),
                    "X-TTS-Speaker-Switches": str(speaker_switches),
                    "X-TTS-Generations": str(generation_count),
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
                    "Tamil answer audio is unavailable; the text answer is unaffected."
                ),
            )
