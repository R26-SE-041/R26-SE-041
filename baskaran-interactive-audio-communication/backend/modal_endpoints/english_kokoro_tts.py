"""Modal endpoint: Kokoro-82M English text-to-speech.

Deploy:
    modal deploy backend/modal_endpoints/english_kokoro_tts.py

Accepts JSON:
    {"text": str, "voice": str (optional), "speed": float (optional)}

Returns 24 kHz, 16-bit PCM WAV bytes. This endpoint handles English only.
"""

import io
import re
import time

import modal
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

MODEL_ID = "hexgrad/Kokoro-82M"
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
SAMPLE_RATE = 24_000
CACHE_DIR = "/models"
HF_CACHE_DIR = f"{CACHE_DIR}/huggingface"
_ENGLISH_VOICE_RE = re.compile(r"^[ab][fm]_[a-z0-9_]+$")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("espeak-ng", "libsndfile1")
    .run_commands(
        "python -m pip install torch==2.4.1 "
        "--index-url https://download.pytorch.org/whl/cpu"
    )
    .pip_install(
        "kokoro>=0.9.4,<1.0",
        "transformers>=4.46,<5",
        "soundfile>=0.12.1",
        "numpy>=1.26,<2",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
    )
    .env({"HF_HOME": HF_CACHE_DIR})
)

app = modal.App("voicelearn-english-kokoro-tts", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)


class EnglishKokoroTTSRequest(BaseModel):
    text: str
    voice: str = Field(default=DEFAULT_VOICE, min_length=1, max_length=64)
    speed: float = Field(default=DEFAULT_SPEED, ge=0.5, le=2.0)


def _validate_english_voice(voice: str) -> str:
    """Accept Kokoro American/British English voice identifiers only."""
    normalized = (voice or DEFAULT_VOICE).strip().lower()
    if not _ENGLISH_VOICE_RE.fullmatch(normalized):
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid English Kokoro voice. Expected an American or British "
                "voice such as 'af_heart', 'am_adam', 'bf_emma', or 'bm_george'."
            ),
        )
    return normalized


@app.cls(
    cpu=4.0,
    memory=4096,
    volumes={CACHE_DIR: model_volume},
    scaledown_window=300,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class EnglishKokoroTTS:
    """Kokoro-82M English synthesis on a lightweight CPU container."""

    @modal.enter()
    def load_model(self):
        from kokoro import KPipeline

        started = time.perf_counter()
        print(f"[EnglishKokoroTTS] Loading {MODEL_ID} on CPU ...")

        # lang_code='a' selects the American-English G2P pipeline. Kokoro also
        # resolves British voices passed at request time from their `b` prefix.
        self._american_pipeline = KPipeline(lang_code="a", repo_id=MODEL_ID)
        self._british_pipeline = KPipeline(lang_code="b", repo_id=MODEL_ID)
        model_volume.commit()

        elapsed = time.perf_counter() - started
        print(f"[EnglishKokoroTTS] Ready in {elapsed:.2f}s (model: {MODEL_ID})")

    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: EnglishKokoroTTSRequest) -> Response:
        import traceback

        import numpy as np
        import soundfile as sf

        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        voice = _validate_english_voice(req.voice)
        pipeline = self._american_pipeline if voice.startswith("a") else self._british_pipeline
        started = time.perf_counter()
        print(
            f"[EnglishKokoroTTS] Synthesizing {len(text)} chars | "
            f"voice={voice} | speed={req.speed:.2f}"
        )

        try:
            waveforms: list[np.ndarray] = []
            generator = pipeline(
                text,
                voice=voice,
                speed=req.speed,
                split_pattern=r"\n+|(?<=[.!?])\s+",
            )

            for _, _, audio in generator:
                if hasattr(audio, "detach"):
                    audio = audio.detach().cpu().numpy()
                waveform = np.asarray(audio, dtype=np.float32).squeeze()
                if waveform.size:
                    waveforms.append(waveform)

            if not waveforms:
                raise HTTPException(status_code=500, detail="Kokoro returned no audio.")

            silence = np.zeros(int(SAMPLE_RATE * 0.12), dtype=np.float32)
            combined = waveforms[0]
            for waveform in waveforms[1:]:
                combined = np.concatenate((combined, silence, waveform))

            peak = float(np.abs(combined).max())
            if peak > 1.0:
                combined = combined / peak * 0.98

            buffer = io.BytesIO()
            sf.write(buffer, combined, SAMPLE_RATE, format="WAV", subtype="PCM_16")

            elapsed = time.perf_counter() - started
            print(
                f"[TIMING] english_kokoro_tts_generation: {elapsed:.3f}s | "
                f"{len(text)} chars | {len(waveforms)} chunk(s) | voice={voice}"
            )
            return Response(
                content=buffer.getvalue(),
                media_type="audio/wav",
                headers={
                    "X-TTS-Engine": "Kokoro-82M",
                    "X-TTS-Voice": voice,
                    "X-TTS-Sample-Rate": str(SAMPLE_RATE),
                },
            )

        except HTTPException:
            raise
        except Exception as exc:
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Kokoro synthesis failed: {type(exc).__name__}: {exc}",
            ) from exc
