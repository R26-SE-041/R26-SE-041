"""Modal endpoint: SinhalaVITS-TTS-F1 — Sinhala female text-to-speech.

Model:   dialoglk/SinhalaVITS-TTS-F1
Voice:   Nipunika (female)
License: MPL-2.0

Deploy:
    modal deploy backend/modal_endpoints/sinhala_vits_tts.py

Accepts JSON:
    { "text": "<Sinhala text>" }

Returns: audio/wav (22,050 Hz, PCM 16-bit)

Response metadata headers:
    X-TTS-Engine:     SinhalaVITS-F1
    X-TTS-Latency-Ms: <round-trip ms>
    X-TTS-Sample-Rate: 22050

This is the final Sinhala answer-audio service. Its dependency environment is
isolated from the main FastAPI process because Coqui TTS uses older audio pins.
"""

import io
import time

import modal
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

# ── Modal infra ────────────────────────────────────────────────────────────────

# Python 3.11 image, completely isolated from the main FastAPI environment.
# TTS==0.21.1 is installed ONLY here — it has old scipy/librosa pins that
# would conflict with the main app. Using debian_slim for minimal footprint.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "libsndfile1",   # soundfile requires libsndfile
        "ffmpeg",        # audio format support
        "espeak-ng",     # eSpeak phonemizer (Coqui TTS dependency)
    )
    .pip_install(
        # TTS 0.21.1 (Coqui TTS) — MUST be pinned to match official model requirements.
        # This installs old scipy/librosa/numba — ISOLATED from main environment.
        "TTS==0.21.1",
        # PyTorch 2.x — compatible with Coqui TTS 0.21.1
        "torch==2.2.2",
        # Audio I/O
        "soundfile>=0.12.1",
        "numpy",
        # Serving
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
        "huggingface_hub>=0.24.0",
    )
)

# Stable app name — URL stored in MODAL_SINHALA_VITS_TTS_URL in backend/.env.
app = modal.App("voicelearn-sinhala-vits-tts", image=image)

# Use the shared Modal volume for model caching.
# Sinhala model is cached under a separate subdirectory so it never conflicts
# with Tamil IndicF5 or English Parler-TTS weights.
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

# HuggingFace repo for the model
HF_REPO = "dialoglk/SinhalaVITS-TTS-F1"

# Verified filenames from the official HuggingFace repository
CHECKPOINT_FILENAME = "Nipunika_210000.pth"
CONFIG_FILENAME = "Nipunika_config.json"
ROMANIZER_FILENAME = "romanizer.py"

CACHE_DIR = "/models"
SINHALA_CACHE = f"{CACHE_DIR}/sinhala-vits-f1"

# Output sample rate (from model README: "Training Sampling rate: 22050 Hz")
SAMPLE_RATE = 22050


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class SinhalaTTSRequest(BaseModel):
    text: str


class RomanizeRequest(BaseModel):
    text: str


# ── Modal class — loads Synthesizer once per container startup ─────────────────

@app.cls(
    # T4 (16 GB VRAM) is more than sufficient for VITS — it's a lightweight
    # single-speaker model trained on ~100 min of data. A10G is not needed.
    gpu="T4",
    volumes={CACHE_DIR: model_volume},
    # Keep warm for 5 minutes after the last request to avoid repeated cold-starts
    # during evaluation sessions.
    scaledown_window=300,
    memory=8192,
    # HuggingFace token (optional — dialoglk/SinhalaVITS-TTS-F1 is public)
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class SinhalaVITSTTS:
    """SinhalaVITS-TTS-F1 (Nipunika female voice) running on Modal T4.

    The Coqui TTS Synthesizer is loaded once at container startup via @modal.enter().
    All romanization is handled by the official romanizer.py from the HuggingFace repo.
    """

    @modal.enter()
    def load_model(self):
        """Download model files and load Synthesizer at container start.

        Files are cached in the Modal Volume so subsequent cold-starts skip
        the HuggingFace download entirely.
        """
        import os
        import sys
        import torch
        from huggingface_hub import hf_hub_download
        from TTS.utils.synthesizer import Synthesizer

        started = time.perf_counter()

        token = os.environ.get("HF_TOKEN")

        print(f"[SinhalaVITS] Preparing model from {HF_REPO} ...")

        os.makedirs(SINHALA_CACHE, exist_ok=True)

        # Download model checkpoint
        checkpoint_path = os.path.join(SINHALA_CACHE, CHECKPOINT_FILENAME)
        if not os.path.exists(checkpoint_path):
            print(f"[SinhalaVITS] Downloading {CHECKPOINT_FILENAME} ...")
            hf_hub_download(
                repo_id=HF_REPO,
                filename=CHECKPOINT_FILENAME,
                local_dir=SINHALA_CACHE,
                token=token,
            )
        else:
            print(f"[SinhalaVITS] Using cached {CHECKPOINT_FILENAME}")

        # Download model config
        config_path = os.path.join(SINHALA_CACHE, CONFIG_FILENAME)
        if not os.path.exists(config_path):
            print(f"[SinhalaVITS] Downloading {CONFIG_FILENAME} ...")
            hf_hub_download(
                repo_id=HF_REPO,
                filename=CONFIG_FILENAME,
                local_dir=SINHALA_CACHE,
                token=token,
            )
        else:
            print(f"[SinhalaVITS] Using cached {CONFIG_FILENAME}")

        # Download official romanizer.py from the HuggingFace repo
        romanizer_path = os.path.join(SINHALA_CACHE, ROMANIZER_FILENAME)
        if not os.path.exists(romanizer_path):
            print(f"[SinhalaVITS] Downloading {ROMANIZER_FILENAME} ...")
            hf_hub_download(
                repo_id=HF_REPO,
                filename=ROMANIZER_FILENAME,
                local_dir=SINHALA_CACHE,
                token=token,
            )
        else:
            print(f"[SinhalaVITS] Using cached {ROMANIZER_FILENAME}")

        # Commit any newly downloaded files to the volume
        model_volume.commit()

        # Add the model cache directory to sys.path so we can import romanizer.py
        # (the official module from the HuggingFace repo)
        if SINHALA_CACHE not in sys.path:
            sys.path.insert(0, SINHALA_CACHE)

        # Import the official romanizer module
        import importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location("romanizer", romanizer_path)
        romanizer_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(romanizer_mod)
        self._sinhala_to_roman = romanizer_mod.sinhala_to_roman
        print("[SinhalaVITS] romanizer.py loaded successfully")

        # Determine compute device
        use_cuda = torch.cuda.is_available()
        self._device = "cuda" if use_cuda else "cpu"
        print(f"[SinhalaVITS] Loading Synthesizer on {self._device} ...")

        # Load the Coqui TTS Synthesizer (exactly as in official inference_F1.py)
        self._synth = Synthesizer(
            tts_checkpoint=checkpoint_path,
            tts_config_path=config_path,
            use_cuda=use_cuda,
        )

        elapsed = time.perf_counter() - started
        print(
            f"[SinhalaVITS] Ready on {self._device} in {elapsed:.2f}s "
            f"(checkpoint: {CHECKPOINT_FILENAME}, sample_rate: {SAMPLE_RATE} Hz)"
        )

    # ── Synthesis endpoint ─────────────────────────────────────────────────────

    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: SinhalaTTSRequest) -> Response:
        """POST / — Synthesize Sinhala text to WAV audio.

        Flow (mirrors official inference_F1.py exactly):
            1. sinhala_to_roman(text)     — Sinhala Unicode → romanized Sinhala
            2. synth.tts(romanized_text)  — VITS synthesis
            3. save_wav(wav, stream)       — 22,050 Hz WAV

        English/Latin words embedded in Sinhala text pass through romanizer.py
        unchanged and are fed directly to VITS. Pronunciation quality for English
        words is unknown — this is the primary unknown to evaluate.

        Returns:
            audio/wav — 22,050 Hz, PCM 16-bit, mono
        """
        import traceback

        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        started = time.perf_counter()

        # Step 1: Romanize Sinhala text using the official romanizer
        romanized = self._sinhala_to_roman(text)
        romanize_elapsed = time.perf_counter() - started

        print(
            f"[SinhalaVITS] Synthesizing {len(text)} chars | "
            f"original[:60]: '{text[:60]}' | "
            f"romanized[:60]: '{romanized[:60]}'"
        )
        print(f"[SinhalaVITS] Romanization took {romanize_elapsed*1000:.1f}ms")

        try:
            # Step 2: VITS synthesis (Coqui Synthesizer API)
            wav = self._synth.tts(romanized)

            # Step 3: Encode as WAV
            out = io.BytesIO()
            self._synth.save_wav(wav, out)
            out.seek(0)
            wav_bytes = out.getvalue()

            elapsed = time.perf_counter() - started
            print(
                f"[TIMING] sinhala_vits_synthesis: {elapsed:.3f}s | "
                f"{len(text)} chars | {len(wav_bytes)} bytes"
            )

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-TTS-Engine": "SinhalaVITS-F1",
                    "X-TTS-Latency-Ms": str(int(elapsed * 1000)),
                    "X-TTS-Sample-Rate": str(SAMPLE_RATE),
                    # Expose for debugging only — remove in production integration
                    "Access-Control-Expose-Headers": (
                        "X-TTS-Engine, X-TTS-Latency-Ms, X-TTS-Sample-Rate"
                    ),
                },
            )

        except HTTPException:
            raise
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[SinhalaVITS] SYNTHESIS ERROR: {exc}\n{tb}")
            raise HTTPException(
                status_code=500,
                detail=f"SinhalaVITS synthesis failed: {type(exc).__name__}: {exc}",
            )

    # ── Romanize preview endpoint ──────────────────────────────────────────────

    @modal.fastapi_endpoint(method="POST")
    def romanize(self, req: RomanizeRequest) -> dict:
        """POST /romanize — Preview the romanizer output WITHOUT synthesis.

        DEVELOPMENT ONLY — used by the temporary /api/v1/test/sinhala-tts/romanize
        backend route and the romanizer debug panel in the frontend test page.

        Returns:
            {
              "original":  "<raw Sinhala text>",
              "romanized": "<romanized output fed to VITS>"
            }

        This is useful for verifying how:
            - Sinhala words are romanized
            - English words are handled (they pass through unchanged)
            - Acronyms behave
        """
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        romanized = self._sinhala_to_roman(text)
        return {"original": text, "romanized": romanized}
