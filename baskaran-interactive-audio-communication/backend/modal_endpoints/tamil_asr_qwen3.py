"""
Modal Serverless Endpoint: lemuralabs/tamil-asr-qwen3 -- Tamil Speech-to-Text
(replaces IndicConformer 600M for Tamil ASR)

Why this instead of IndicConformer?
  lemuralabs/tamil-asr-qwen3 is a Qwen3-ASR fine-tune specifically trained on
  Tamil speech.  It uses an audio encoder (AuT) + Qwen3 LLM decoder, which
  gives much higher accuracy on conversational / educational Tamil compared to
  IndicConformer's CTC decoder.

  Accessible via the HuggingFace id:
    osmapi/tamil-asr-qwen3  (mirror of lemuralabs/tamil-asr-qwen3)

Architecture:
  - Audio Encoder (AuT): Fbank 128-dim features -> attention-based encoder
  - Text Decoder: Qwen3 LLM (28-layer GQA + RoPE + SwiGLU)
  - Decoding is handled by the qwen-asr toolkit
  - Input: 16 kHz mono WAV

Deploy:
    modal deploy backend/modal_endpoints/tamil_asr_qwen3.py

Then set in .env:
    MODAL_INDIC_STT_URL=<the new endpoint URL printed after deploy>

The backend already routes Tamil -> MODAL_INDIC_STT_URL automatically,
so no other changes are needed.

Usage:
    POST multipart/form-data
      audio_file: <audio bytes>   (wav/webm/mp3 -- ffmpeg resamples to 16kHz mono)
      language_hint: "tamil"      (only "tamil" supported; others raise 400)
"""

import tempfile
import time

import modal
from fastapi import Form, UploadFile
from fastapi.responses import JSONResponse

# -- Modal image ---------------------------------------------------------------
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install("ffmpeg")
    .pip_install(
        # Torch 2.2.2/native extensions in this image require the NumPy 1.x ABI.
        # Keep this exact constraint in the same pip transaction so later
        # dependencies cannot resolve NumPy 2.x.
        "numpy==1.26.4",
        "torch==2.2.2",
        "torchaudio==2.2.2",
        # Transformers 4.46+ required for Qwen3-ASR model class support
        "transformers>=4.46.0",
        "huggingface_hub>=0.22.0",
        "fastapi[standard]==0.115.0",
        # Qwen3-ASR toolkit (official; gives the transcribe() helper)
        "qwen-asr>=0.0.6",
        # soundfile for audio I/O
        "soundfile>=0.12.1",
        # accelerate for device_map support
        "accelerate>=0.26.0",
    )
)

app = modal.App("voicelearn-tamil-asr-qwen3", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

# Model ID -- osmapi/tamil-asr-qwen3 mirrors lemuralabs/tamil-asr-qwen3
_MODEL_ID = "osmapi/tamil-asr-qwen3"
_CACHE_DIR = "/models/tamil-asr-qwen3"

_SUPPORTED = {"tamil"}


@app.cls(
    gpu="A10G",   # Qwen3 decoder needs more VRAM than IndicConformer; A10G (24 GB) is safe
    volumes={"/models": model_volume},
    scaledown_window=300,
    memory=16384,  # 16 GB host RAM -- model weights + torchaudio
)
class TamilASRQwen3:

    @modal.enter()
    def load_model(self):
        """
        Download and load lemuralabs/tamil-asr-qwen3 via the qwen-asr toolkit.

        The qwen-asr Qwen3ASRModel.from_pretrained() handles:
          - Downloading the model from HuggingFace Hub
          - Loading the audio encoder + Qwen3 decoder
          - Moving everything to the correct device (cuda:0 via device_map)

        Model is cached in /models (Modal Volume) so cold-starts after the
        first download take only a few seconds.
        """
        import numpy as np
        import torch
        from qwen_asr import Qwen3ASRModel

        print(f"[TamilASRQwen3] numpy={np.__version__} torch={torch.__version__}")
        print(f"[TamilASRQwen3] Loading {_MODEL_ID} ...")
        self.model = Qwen3ASRModel.from_pretrained(
            _MODEL_ID,
            device_map="cuda:0",
            dtype=torch.bfloat16,
            cache_dir=_CACHE_DIR,
        )
        print("[TamilASRQwen3] Model ready.")

    # -- helpers ---------------------------------------------------------------

    def _audio_to_wav_file(self, audio_bytes: bytes, original_filename: str) -> str:
        """
        Write audio bytes to a temp WAV file resampled to 16 kHz mono.

        The qwen-asr toolkit's .transcribe() accepts a file path directly,
        so we just need to give it a properly formatted file.
        """
        import torchaudio
        import torch

        ext = ".webm"
        if original_filename:
            for candidate in (".wav", ".webm", ".mp3", ".ogg", ".m4a", ".mp4"):
                if original_filename.lower().endswith(candidate):
                    ext = candidate
                    break

        # Write raw bytes to temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
            tmp_in.write(audio_bytes)
            tmp_in_path = tmp_in.name

        # Load, mix to mono, resample to 16 kHz
        wav, sr = torchaudio.load(tmp_in_path)
        if wav.shape[0] > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)
        if sr != 16_000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16_000)
            wav = resampler(wav)

        # Write normalised WAV to output temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
            torchaudio.save(tmp_out.name, wav, 16_000)
            return tmp_out.name

    # -- endpoint --------------------------------------------------------------

    @modal.fastapi_endpoint(method="POST")
    async def transcribe(
        self,
        audio_file: "UploadFile",
        language_hint: str = Form("tamil"),
    ):
        """
        Transcribe Tamil audio using lemuralabs/tamil-asr-qwen3 (Qwen3 decoder).

        Returns:
            {
                "transcript":        str,   # Tamil Unicode text
                "detected_language": "ta",
                "duration_ms":       int
            }
        """
        if audio_file is None:
            return JSONResponse({"error": "audio_file is required"}, status_code=400)

        lang = language_hint.lower()
        if lang not in _SUPPORTED:
            return JSONResponse(
                {"error": f"TamilASRQwen3 only supports: {list(_SUPPORTED)}. Got '{lang}'"},
                status_code=400,
            )

        audio_bytes = await audio_file.read()
        if not audio_bytes:
            return JSONResponse({"error": "audio_file is empty"}, status_code=400)

        start = time.perf_counter()

        try:
            # Convert to 16 kHz mono WAV and get temp file path
            wav_path = self._audio_to_wav_file(audio_bytes, audio_file.filename or "recording.webm")

            # qwen-asr's transcribe API does not accept transformers-style
            # num_beams. Decoding remains the toolkit/model default.
            results = self.model.transcribe(audio=wav_path)

            if isinstance(results, list) and results:
                transcript = results[0].text.strip()
            elif hasattr(results, "text"):
                transcript = results.text.strip()
            else:
                transcript = str(results).strip()

        except Exception as exc:
            print(f"[TamilASRQwen3] Inference error: {exc}")
            return JSONResponse(
                {"error": f"Transcription failed: {exc}"},
                status_code=500,
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        preview = transcript[:60] if transcript else ""
        print(f"[TamilASRQwen3] '{preview}...' | lang=ta | {elapsed_ms}ms")
        print(f"[LATENCY] ASR tamil qwen = {elapsed_ms / 1000:.3f}s")
        print("[LATENCY] ASR tamil fallback_used=false")
        print(f"[LATENCY] ASR TOTAL = {elapsed_ms / 1000:.3f}s")

        return {
            "transcript":        transcript,
            "detected_language": "ta",
            "duration_ms":       elapsed_ms,
        }


@app.local_entrypoint()
def test():
    print(
        "TamilASRQwen3 endpoint ready.\n"
        "Deploy with:\n"
        "  modal deploy backend/modal_endpoints/tamil_asr_qwen3.py\n"
        "Then set MODAL_INDIC_STT_URL=<printed URL> in your .env"
    )

