"""
Modal Serverless Endpoint: MMS-TTS — Text-to-Speech

Deploy:
    modal deploy backend/modal_endpoints/tts.py

Accepts JSON:
    { "text": str, "language": str }

Returns: audio/wav bytes (raw WAV file)

MMS-TTS supports 1100+ languages including Tamil (tam) and Sinhala (sin).
"""

import io

import modal
from fastapi.responses import Response
from pydantic import BaseModel

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers==4.45.0",
        "torch==2.2.0",
        "scipy==1.11.4",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
    )
)

app = modal.App("voicelearn-tts", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

# MMS-TTS language codes
LANG_TO_MMS = {
    "english": "eng",
    "tamil":   "tam",
    "sinhala": "sin",
    "mixed":   "eng",  # Mixed uses English TTS; text already localized
}


class TTSRequest(BaseModel):
    text: str
    language: str = "english"


@app.cls(
    gpu="T4",
    volumes={"/models": model_volume},
    scaledown_window=300,
    memory=4096,
)
class MMSTTS:
    @modal.enter()
    def load_model(self):
        # Pre-load English as default; other languages loaded on first request.
        self._models: dict = {}
        self._tokenizers: dict = {}
        self._load_lang("eng")

    def _load_lang(self, lang_code: str):
        from transformers import VitsModel, AutoTokenizer

        if lang_code in self._models:
            return

        model_id = f"facebook/mms-tts-{lang_code}"
        self._tokenizers[lang_code] = AutoTokenizer.from_pretrained(
            model_id, cache_dir="/models"
        )
        self._models[lang_code] = VitsModel.from_pretrained(
            model_id, cache_dir="/models"
        )

    # -- benchmark introspection (warm-latency + GPU table for the paper) ------
    @modal.fastapi_endpoint(method="GET")
    def gpu_info(self):
        """Report the physical accelerator serving this warm container.

        The `gpu=` argument in @app.cls names the requested class, not the
        device string a paper has to cite. Call this straight after a warm
        latency batch: it lands on the already-running container, so it adds
        no cold start and no measurable GPU time.
        """
        try:
            import torch
        except Exception as exc:            # torch absent (CPU-only image)
            return {
                "endpoint": "mms_tts",
                "model_id": "facebook/mms-tts-{lang}",
                "requested_gpu": "T4",
                "gpu_name": "CPU",
                "device": "cpu",
                "vram_total_gb": None,
                "torch_version": None,
                "note": f"torch unavailable: {type(exc).__name__}",
            }

        cuda = torch.cuda.is_available()
        return {
            "endpoint": "mms_tts",
            "model_id": "facebook/mms-tts-{lang}",
            "requested_gpu": "T4",
            "gpu_name": torch.cuda.get_device_name(0) if cuda else "CPU",
            "device": "cuda" if cuda else "cpu",
            "vram_total_gb": (
                round(torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 1)
                if cuda
                else None
            ),
            "torch_version": torch.__version__,
        }

    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: TTSRequest) -> Response:
        import torch
        import scipy.io.wavfile

        text: str = (req.text or "").strip()
        language: str = (req.language or "english").lower()

        lang_code = LANG_TO_MMS.get(language, "eng")
        self._load_lang(lang_code)

        tokenizer = self._tokenizers[lang_code]
        model = self._models[lang_code]

        inputs = tokenizer(text, return_tensors="pt")

        with torch.no_grad():
            output = model(**inputs).waveform

        waveform = output.squeeze().numpy()
        sample_rate = model.config.sampling_rate

        buf = io.BytesIO()
        scipy.io.wavfile.write(buf, sample_rate, waveform)
        buf.seek(0)

        return Response(content=buf.read(), media_type="audio/wav")

