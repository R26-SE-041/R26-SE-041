"""
Modal Serverless Endpoint: Sinhala Whisper ASR -- Speech-to-Text (Sinhala only)

ISOLATED EXPERIMENT -- DO NOT connect to RAG, TTS, or any existing pipeline.

Model: Lingalingeswaran/whisper-small-sinhala
  Base: openai/whisper-small (~241.7M params, WhisperForConditionalGeneration)
  Fine-tuned on: Mozilla Common Voice 11.0 Sinhala subset
  No trust_remote_code needed. License: Apache 2.0.

Why a separate Modal app?
  Tamil ASR  -> voicelearn-indic-stt    (IndicConformer CTC)
  English ASR -> voicelearn-whisper-stt (faster-whisper large-v3)
  Sinhala ASR -> voicelearn-sinhala-whisper-asr  (THIS FILE -- ISOLATED)

Inference: transcription only (NOT translation).
  language="si" (Sinhala ISO 639-1), task="transcribe"

Audio: WAV / MP3 / M4A / WebM -> 16 kHz mono (torchaudio + ffmpeg)

Endpoint: POST /  multipart/form-data  field=audio_file
Response: {"text": "...", "latency_ms": 1234, "duration_seconds": 5.2, "engine": "..."}

Deploy:
    modal deploy backend/modal_endpoints/sinhala_whisper_asr.py
Then set:
    MODAL_SINHALA_ASR_URL=<printed URL>
"""

import tempfile
import time

import modal
from fastapi import UploadFile
from fastapi.responses import JSONResponse

_MODEL_ID = "Lingalingeswaran/whisper-small-sinhala"
_MODEL_CACHE = "/model-cache"


def _download_model() -> None:
    """Bake the one permitted Sinhala ASR model into the Modal image."""
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=_MODEL_ID, cache_dir=_MODEL_CACHE)


image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install("ffmpeg")
    .pip_install(
        # torch 2.2 wheels require NumPy 1.x. Without this pin, a fresh image
        # can install NumPy 2.x and fail while converting audio to numpy.
        "numpy>=1.24,<2",
        "torch==2.2.2",
        "torchaudio==2.2.2",
        # This fine-tuned checkpoint uses Whisper's forced_decoder_ids API.
        # Newer Transformers releases removed that generate() argument.
        "transformers==4.40.2",
        "huggingface_hub==0.22.2",
        "fastapi[standard]==0.115.0",
        "soundfile>=0.12.1",
    )
    # Download at deploy/build time instead of during the first request. This
    # removes the largest source of cold-start request timeouts.
    .run_function(_download_model, timeout=30 * 60)
)

app = modal.App("voicelearn-sinhala-whisper-asr", image=image)


@app.cls(
    gpu="T4",
    scaledown_window=300,
    memory=4096,
    timeout=10 * 60,
)
class SinhalaWhisperASR:

    @modal.enter()
    def load_model(self):
        """Load model once at container startup. fp16 on CUDA, fp32 on CPU."""
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        print(f"[SinhalaWhisperASR] Loading {_MODEL_ID} ...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype  = torch.float16 if self.device == "cuda" else torch.float32
        cache_dir = _MODEL_CACHE

        self.processor = WhisperProcessor.from_pretrained(
            _MODEL_ID, cache_dir=cache_dir,
        )
        self.model = WhisperForConditionalGeneration.from_pretrained(
            _MODEL_ID, torch_dtype=self.dtype, cache_dir=cache_dir,
        ).to(self.device)
        self.model.eval()

        # This checkpoint's config.json contains the legacy forced_decoder_ids
        # field. Even the language/task helper in this Transformers release
        # converts its values back into that rejected argument. Build the same
        # Sinhala/transcribe/no-timestamps prefix as decoder_input_ids instead.
        self.model.config.forced_decoder_ids = None
        self.model.generation_config.forced_decoder_ids = None
        self.model.generation_config.language = None
        self.model.generation_config.task = None
        prompt_ids = self.processor.get_decoder_prompt_ids(
            language="si", task="transcribe", no_timestamps=True,
        )
        decoder_prefix = [self.model.config.decoder_start_token_id]
        decoder_prefix.extend(token_id for _, token_id in prompt_ids)
        self.decoder_input_ids = torch.tensor(
            [decoder_prefix], dtype=torch.long, device=self.device,
        )
        print(
            f"[SinhalaWhisperASR] Ready on {self.device} ({self.dtype}) | "
            "language=si, task=transcribe"
        )

    def _load_audio_16k_mono(self, audio_bytes: bytes, original_filename: str):
        """Decode any audio format -> 16 kHz mono numpy float32 array."""
        import torch
        import torchaudio

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

        if wav.shape[0] > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)

        if sr != 16_000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16_000)
            wav = resampler(wav)

        duration_seconds = wav.shape[-1] / 16_000
        return wav.squeeze().numpy().astype("float32"), duration_seconds

    @modal.fastapi_endpoint(method="POST")
    async def transcribe(self, audio_file: "UploadFile"):
        """
        Sinhala audio -> Sinhala Unicode transcript (TRANSCRIPTION, not translation).

        Input:  multipart/form-data, field=audio_file (WAV/MP3/M4A/WebM)
        Output: {"text": "...", "latency_ms": int, "duration_seconds": float, "engine": str}
        """
        import torch

        if audio_file is None:
            return JSONResponse({"error": "audio_file is required"}, status_code=400)
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            return JSONResponse({"error": "audio_file is empty"}, status_code=400)

        filename = audio_file.filename or "recording.webm"
        start = time.perf_counter()

        try:
            from transformers.generation.utils import GenerationMixin

            wav_numpy, duration_seconds = self._load_audio_16k_mono(audio_bytes, filename)

            inputs = self.processor(
                wav_numpy, sampling_rate=16_000, return_tensors="pt",
            )
            input_features = inputs.input_features.to(self.device, dtype=self.dtype)

            with torch.no_grad():
                # The Whisper-specific generate wrapper in this dependency
                # combination injects the removed forced_decoder_ids kwarg.
                # The base generation engine accepts our explicit decoder
                # prefix and runs the same model without that broken wrapper.
                predicted_ids = GenerationMixin.generate(
                    self.model,
                    inputs=input_features,
                    decoder_input_ids=self.decoder_input_ids,
                )

            transcript = self.processor.batch_decode(
                predicted_ids, skip_special_tokens=True,
            )
            if isinstance(transcript, list):
                transcript = " ".join(t.strip() for t in transcript if t.strip())
            else:
                transcript = str(transcript).strip()

        except Exception as exc:
            import traceback

            traceback.print_exc()
            print(f"[SinhalaWhisperASR] Inference error: {exc}")
            return JSONResponse({"error": f"Transcription failed: {exc}"}, status_code=500)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        warmth = "cold-start" if elapsed_ms > 15_000 else "warm"
        print(f"[SinhalaWhisperASR] {repr(transcript[:80])} | {elapsed_ms}ms ({warmth}) | audio={duration_seconds:.2f}s")

        return {
            "text":             transcript,
            "latency_ms":       elapsed_ms,
            "duration_seconds": round(duration_seconds, 3),
            "engine":           _MODEL_ID,
        }


@app.local_entrypoint()
def test():
    print("Deploy: modal deploy backend/modal_endpoints/sinhala_whisper_asr.py")
