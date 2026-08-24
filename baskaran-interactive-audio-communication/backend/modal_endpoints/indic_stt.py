"""
Modal Serverless Endpoint: IndicConformer 600M — Tamil Speech-to-Text

Why this instead of Whisper for Tamil?
  Whisper is a generic multilingual model trained mostly on English/European data.
  Tamil is ~1% of its training set, so it frequently:
    - Romanizes Tamil speech (outputs "naai" instead of "நாய்")
    - Requires hacky ASCII token suppression + script correction fallbacks

  ai4bharat/indic-conformer-600m-multilingual is trained natively on all 22
  Indian languages including Tamil.  It always outputs correct Unicode Tamil
  with no suppression tricks needed.

Architecture:
  - Conformer encoder (self-attention + depthwise conv) — great for tonal/agglutinative langs
  - CTC decoder — fast, non-autoregressive (no beam search delay)
  - Input: 16 kHz mono WAV (matches our frontend recording settings)

Deploy:
    modal deploy backend/modal_endpoints/indic_stt.py

Usage:
    POST multipart/form-data
      audio_file: <audio bytes>   (wav/webm/mp3 — ffmpeg resamples to 16kHz mono)
      language_hint: "tamil"      (only "tamil" supported; others raise 400)
"""

import io
import tempfile
import time

import modal
from fastapi import Form, UploadFile
from fastapi.responses import JSONResponse

# ── Modal image ───────────────────────────────────────────────────────────────
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install("ffmpeg")
    .pip_install(
        "torch==2.2.2",
        "torchaudio==2.2.2",
        "transformers>=4.40.0",
        "huggingface_hub>=0.22.0",
        "fastapi[standard]==0.115.0",
        # ONNX runtime needed by IndicConformer's custom model code
        "onnx>=1.16.0",
        "onnxruntime-gpu>=1.18.0",
        # soundfile for audio I/O
        "soundfile>=0.12.1",
    )
)

app = modal.App("voicelearn-indic-stt", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

# IndicConformer language codes for supported languages
# We only route Tamil here; expand as needed
_SUPPORTED = {"tamil": "ta"}


@app.cls(
    gpu="T4",
    volumes={"/models": model_volume},
    scaledown_window=300,
    memory=6144,   # 6 GB — model + torchaudio + ONNX runtime
)
class IndicSTT:

    @modal.enter()
    def load_model(self):
        """
        Load IndicConformer 600M multilingual from HuggingFace.

        trust_remote_code=True is required because the model ships custom
        modeling code (conformer + CTC/RNNT decoders) not yet in transformers core.

        The model is cached in /models (Modal Volume) so subsequent cold-starts
        skip the ~2 GB download.
        """
        from transformers import AutoModel

        print("[IndicSTT] Loading ai4bharat/indic-conformer-600m-multilingual …")
        self.model = AutoModel.from_pretrained(
            "ai4bharat/indic-conformer-600m-multilingual",
            trust_remote_code=True,
            cache_dir="/models/indic-conformer",
        )
        self.model.eval()
        print("[IndicSTT] Model ready.")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _load_audio_as_16k_mono(self, audio_bytes: bytes, original_filename: str):
        """
        Convert any audio format to a 16 kHz mono waveform tensor.

        Strategy:
          1. Write raw bytes to a temp file (preserving extension for ffmpeg)
          2. Use torchaudio.load() — it auto-selects the right backend
          3. Mix down to mono (mean of channels)
          4. Resample to 16 000 Hz if needed
        """
        import torchaudio
        import torch

        # Determine extension for ffmpeg format detection
        ext = ".webm"
        if original_filename:
            for candidate in (".wav", ".webm", ".mp3", ".ogg", ".m4a", ".mp4"):
                if original_filename.lower().endswith(candidate):
                    ext = candidate
                    break

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        wav, sr = torchaudio.load(tmp_path)

        # Mix stereo → mono
        if wav.shape[0] > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)

        # Resample to 16 kHz (IndicConformer requirement)
        if sr != 16_000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16_000)
            wav = resampler(wav)

        return wav  # shape: (1, num_samples)

    # ── endpoint ──────────────────────────────────────────────────────────────

    @modal.fastapi_endpoint(method="POST")
    async def transcribe(
        self,
        audio_file: "UploadFile",
        language_hint: str = Form("tamil"),
    ):
        """
        Transcribe Tamil audio using IndicConformer CTC decoder.

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
                {"error": f"IndicSTT only supports: {list(_SUPPORTED.keys())}. Got '{lang}'"},
                status_code=400,
            )

        audio_bytes = await audio_file.read()
        if not audio_bytes:
            return JSONResponse({"error": "audio_file is empty"}, status_code=400)

        iso_code = _SUPPORTED[lang]   # "ta"
        start = time.perf_counter()

        try:
            wav = self._load_audio_as_16k_mono(audio_bytes, audio_file.filename or "recording.webm")

            # IndicConformer inference — CTC decoding is fast & deterministic
            # model(waveform_tensor, language_iso, decoder_type)
            transcript = self.model(wav, iso_code, "ctc")

            # model() returns a list of strings or a plain string depending on version
            if isinstance(transcript, (list, tuple)):
                transcript = " ".join(str(t) for t in transcript).strip()
            else:
                transcript = str(transcript).strip()

        except Exception as exc:
            print(f"[IndicSTT] Inference error: {exc}")
            return JSONResponse(
                {"error": f"Transcription failed: {exc}"},
                status_code=500,
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        print(f"[IndicSTT] '{transcript[:60]}…' | lang={iso_code} | {elapsed_ms}ms")

        return {
            "transcript":        transcript,
            "detected_language": iso_code,
            "duration_ms":       elapsed_ms,
        }


@app.local_entrypoint()
def test():
    print("IndicSTT endpoint ready. Use 'modal deploy backend/modal_endpoints/indic_stt.py' to publish.")
