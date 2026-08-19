"""Modal endpoint: AI4Bharat IndicF5 Tamil text-to-speech.

Deploy:
    modal deploy backend/modal_endpoints/tamil_parler_tts.py

The filename and Modal app name intentionally remain unchanged so the existing
MODAL_TAMIL_TTS_URL integration continues to work without any other changes.
"""

import io
import re
import time
from pathlib import Path
from typing import List
from urllib.request import urlretrieve

import modal
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel


image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "libsndfile1",
        "git",
        "ffmpeg",
        # Required by Mode B phonetic normalizer (eSpeak NG G2P layer).
        # espeak-ng -q --ipa=3 -v en-us <word> is called via subprocess on CPU.
        "espeak-ng",
    )
    # ── pip install strategy ──────────────────────────────────────────────────
    # Several packages in this dependency tree ship ONLY as source tarballs
    # (sdists) with non-ASCII characters in their PKG-INFO metadata:
    #   • jieba 0.42.1  — Chinese characters in description
    #   • encodec 0.1.1 — non-ASCII characters in metadata (dep of vocos→f5-tts)
    # When pip downloads and inspects these tarballs, it writes the metadata to
    # stdout.  Modal's local Windows client receives this output and tries to
    # display it using the cp1252 codec, which cannot encode non-ASCII chars →
    # UnicodeEncodeError.  No -X utf8 / PYTHONIOENCODING flag on the remote pip
    # process can fix the Windows-side display codec.
    #
    # Fix: redirect ALL pip stdout+stderr to a file on the remote Linux server
    # so zero non-ASCII characters ever reach the Windows client.
    # On success: only "pip install: OK" (ASCII) is printed.
    # On failure: the log is cat'd with tr stripping non-ASCII, then exit 1.
    #
    # jieba must be pre-installed before IndicF5 so the main install finds it.
    .run_commands(
        "pip install jieba==0.42.1 > /tmp/jieba_install.log 2>&1 "
        "&& echo 'jieba install: OK' "
        "|| (echo 'jieba install FAILED:'; "
        "cat /tmp/jieba_install.log | tr -d '\\200-\\377'; exit 1)"
    )
    .run_commands(
        "pip install "
        "  'torch>=2.1.0' "
        "  'numpy>=1.24.0' "
        "  'git+https://github.com/AI4Bharat/IndicF5.git' "
        "  'transformers<4.50' "
        "  'soundfile>=0.12.1' "
        "  'scipy>=1.11.4' "
        "  'fastapi[standard]>=0.115.0' "
        "  'pydantic>=2.0.0' "
        "  'huggingface_hub>=0.24.0' "
        "  'torchcodec' "
        "> /tmp/main_install.log 2>&1 "
        "&& echo 'main pip install: OK' "
        "|| (echo 'main pip install FAILED:'; "
        "cat /tmp/main_install.log | tr -d '\\200-\\377'; exit 1)"
    )
)

# Keep this app name stable: its deployed web endpoint is stored in
# MODAL_TAMIL_TTS_URL by the existing backend configuration.
app = modal.App("voicelearn-tamil-parler-tts", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

MODEL_ID = "ai4bharat/IndicF5"
CACHE_DIR = "/models"
REFERENCE_AUDIO_PATH = f"{CACHE_DIR}/indicf5/TAM_F_HAPPY_00001.wav"
REFERENCE_AUDIO_URL = (
    "https://github.com/AI4Bharat/IndicF5/raw/refs/heads/main/"
    "prompts/TAM_F_HAPPY_00001.wav"
)
REFERENCE_TEXT = (
    "நான் நெனச்ச மாதிரியே அமேசான்ல பெரிய தள்ளுபடி வந்திருக்கு. "
    "கம்மி காசுக்கே அந்தப் புது சேம்சங் மாடல வாங்கிடலாம்."
)
SAMPLE_RATE = 24000

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.\u0964!?])\s+|\n+")
MAX_CHUNK_CHARS = 400


class TTSRequest(BaseModel):
    text: str
    language: str = "tamil"


def _split_tamil_text(text: str) -> List[str]:
    """Split text at sentence boundaries without cutting words."""
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


@app.cls(
    gpu="A10G",
    volumes={CACHE_DIR: model_volume},
    scaledown_window=300,
    memory=8192,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class TamilIndicF5TTS:
    """IndicF5 Tamil synthesis using AI4Bharat's supplied Tamil voice prompt."""

    @modal.enter()
    def load_model(self):
        import os
        import torch
        from transformers import AutoModel

        started = time.perf_counter()
        token = os.environ.get("HF_TOKEN")
        reference_path = Path(REFERENCE_AUDIO_PATH)
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        if not reference_path.exists():
            print("[TamilIndicF5TTS] Downloading the official Tamil reference prompt ...")
            urlretrieve(REFERENCE_AUDIO_URL, reference_path)
            model_volume.commit()  # persist across container restarts

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[TamilIndicF5TTS] Loading {MODEL_ID} ...")
        self._model = AutoModel.from_pretrained(
            MODEL_ID,
            cache_dir=CACHE_DIR,
            token=token,
            trust_remote_code=True,
        ).to(self._device)
        self._model.eval()
        print(f"[TamilIndicF5TTS] Ready on {self._device} in {time.perf_counter() - started:.2f}s")

    # NOTE: sync (not async) — torch/numpy inference is blocking CPU/GPU work.
    # Modal runs sync @fastapi_endpoint methods in a thread pool automatically.
    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: TTSRequest) -> Response:
        import traceback
        import numpy as np
        import soundfile as sf
        import torch

        text = (req.text or "").strip()
        language = (req.language or "").lower().strip()
        if language != "tamil":
            raise HTTPException(status_code=400, detail="This endpoint only supports language='tamil'.")
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        started = time.perf_counter()
        print(f"[TamilIndicF5TTS] Synthesizing {len(text)} chars ...")

        try:
            waveforms: List[np.ndarray] = []
            for chunk in _split_tamil_text(text):
                print(f"[TamilIndicF5TTS] chunk ({len(chunk)} chars): {chunk[:60]}")
                with torch.inference_mode():
                    audio = self._model(
                        chunk,
                        ref_audio_path=REFERENCE_AUDIO_PATH,
                        ref_text=REFERENCE_TEXT,
                    )
                # IndicF5 may return a torch tensor or numpy array
                if hasattr(audio, "cpu"):
                    audio = audio.cpu().numpy()
                waveform = np.asarray(audio)
                if waveform.dtype == np.int16:
                    waveform = waveform.astype(np.float32) / 32768.0
                else:
                    waveform = waveform.astype(np.float32)
                waveforms.append(waveform.squeeze())

            if not waveforms:
                raise HTTPException(
                    status_code=500,
                    detail="IndicF5 returned no audio — text splitting produced 0 chunks.",
                )

            silence = np.zeros(int(SAMPLE_RATE * 0.2), dtype=np.float32)
            combined = waveforms[0]
            for waveform in waveforms[1:]:
                combined = np.concatenate((combined, silence, waveform))
            buffer = io.BytesIO()
            sf.write(buffer, combined, SAMPLE_RATE, format="WAV", subtype="PCM_16")
            elapsed = time.perf_counter() - started
            print(f"[TIMING] tamil_indicf5_generation: {elapsed:.3f}s | {len(text)} chars")
            return Response(content=buffer.getvalue(), media_type="audio/wav")

        except HTTPException:
            raise
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[TamilIndicF5TTS] SYNTHESIS ERROR: {exc}\n{tb}")
            raise HTTPException(
                status_code=500,
                detail=f"IndicF5 synthesis failed: {type(exc).__name__}: {exc}",
            )
