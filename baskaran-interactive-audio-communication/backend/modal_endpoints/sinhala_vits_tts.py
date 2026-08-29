"""Modal endpoint: dialoglk/SinhalaVITS-TTS-M2 — Sinhala male text-to-speech.

Model:   dialoglk/SinhalaVITS-TTS-M2  (Roshan — male voice)
         Trained by Dialog Axiata PLC + University of Moratuwa
         License: MPL-2.0
Arch:    VITS (Coqui TTS 0.22.0, CUDA-accelerated)
Romanizer: sinhala_to_roman() converts Sinhala Unicode -> ISO 15919 romanization
           before VITS inference (VITS phonemizer expects Latin characters).

Deploy:
    modal deploy backend/modal_endpoints/sinhala_vits_tts.py

Same Modal app name ("voicelearn-sinhala-vits-tts") and same
MODAL_SINHALA_VITS_TTS_URL env variable — no other changes needed.
"""

import io
import re
import time
from pathlib import Path

import modal
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

# -- Image ----------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "libsndfile1",   # soundfile dependency
        "ffmpeg",        # audio processing
        "espeak-ng",     # phonemizer dependency for Coqui TTS
    )
    .run_commands(
        # TTS==0.22.0 is the last stable Coqui TTS release.
        # Pin torch 2.2.0 + numpy<2 to avoid ABI mismatches.
        "pip install "
        "  'torch==2.2.0' "
        "  'torchaudio==2.2.0' "
        "  'TTS==0.22.0' "
        "  'numpy>=1.26,<2' "
        "  'soundfile>=0.12.1' "
        "  'fastapi[standard]>=0.115.0' "
        "  'pydantic>=2.0.0' "
        "  'huggingface_hub>=0.24.0' "
        "> /tmp/tts_install.log 2>&1 "
        "&& echo 'TTS install: OK' "
        "|| (echo 'TTS install FAILED:'; "
        "cat /tmp/tts_install.log | tr -d '\\200-\\377'; exit 1)"
    )
)

app = modal.App("voicelearn-sinhala-vits-tts", image=image)

# Shared volume -- model weights cached after first download (~950 MB)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

MODEL_REPO   = "dialoglk/SinhalaVITS-TTS-M2"
MODEL_FILE   = "Roshan_270000.pth"
CONFIG_FILE  = "Roshan_config.json"
MODELS_DIR   = "/models/sinhala-vits-m2"
SAMPLE_RATE  = 22050   # VITS model sample rate


# -- Romanizer (from dialoglk/SinhalaVITS-TTS-M2/romanizer.py) -----------------
# Converts Sinhala Unicode -> ISO 15919 romanization so VITS can phonemize it.

ro_specials = [
    ['ඓ', 'ai'], ['ඖ', 'au'], ['ඍ', 'r'], ['ඎ', 'r'], ['ඐ', 'l'],
    ['අ', 'a'],  ['ආ', 'aa'], ['ඇ', 'ae'], ['ඈ', 'ae'],
    ['ඉ', 'i'],  ['ඊ', 'ii'], ['උ', 'u'],  ['ඌ', 'uu'],
    ['එ', 'e'],  ['ඒ', 'ee'], ['ඔ', 'o'],  ['ඕ', 'oo'],
    ['ඞ්', 'n'], ['ං', 'm'],  ['ඃ', 'h'],
]

ro_consonants = [
    ['ඛ', 'kh'], ['ඨ', 'th'], ['ඝ', 'gh'], ['ඡ', 'ch'], ['ඣ', 'jh'],
    ['ඦ', 'nj'], ['ඪ', 'dh'], ['ඬ', 'nd'], ['ථ', 'th'], ['ධ', 'dh'],
    ['ඵ', 'ph'], ['භ', 'bh'], ['ඹ', 'mb'], ['ඳ', 'nd'], ['ඟ', 'ng'],
    ['ඥ', 'gn'], ['ක', 'k'],  ['ග', 'g'],  ['ච', 'c'],  ['ජ', 'j'],
    ['ඤ', 'n'],  ['ට', 't'],  ['ඩ', 'd'],  ['ණ', 'n'],  ['ත', 't'],
    ['ද', 'd'],  ['න', 'n'],  ['ප', 'p'],  ['බ', 'b'],  ['ම', 'm'],
    ['ය', 'y'],  ['ර', 'r'],  ['ල', 'l'],  ['ව', 'v'],  ['ශ', 'sh'],
    ['ෂ', 'sh'], ['ස', 's'],  ['හ', 'h'],  ['ළ', 'l'],  ['ෆ', 'f'],
]

ro_combinations = [
    ['', '',    '්'], ['', 'a',   ''],  ['', 'aa',  'ා'],
    ['', 'ae',  'ැ'], ['', 'ae',  'ෑ'], ['', 'i',   'ි'],
    ['', 'ii',  'ී'], ['', 'u',   'ු'], ['', 'uu',  'ූ'],
    ['', 'e',   'ෙ'], ['', 'ee',  'ේ'], ['', 'ai',  'ෛ'],
    ['', 'o',   'ො'], ['', 'oo',  'ෝ'], ['', 'r',   'ෘ'],
    ['', 'rr',  'ෲ'], ['', 'au',  'ෞ'], ['', 'l',   'ෳ'],
]


def _create_conso_combi(combinations, consonants):
    result = []
    for combi in combinations:
        for conso in consonants:
            base_sinh = conso[0] + combi[2]
            base_rom  = combi[0] + conso[1] + combi[1]
            result.append((base_sinh, base_rom))
    return result


_ro_conso_combi = _create_conso_combi(ro_combinations, ro_consonants)


def _replace_all(text, mapping):
    mapping = sorted(mapping, key=lambda x: len(x[0]), reverse=True)
    for sinh, rom in mapping:
        text = re.sub(re.escape(sinh), rom, text)
    return text


def sinhala_to_roman(text):
    """Convert Sinhala Unicode to romanization for VITS phonemizer."""
    text = text.replace("\u200d", "")     # remove Zero-Width Joiner
    text = _replace_all(text, _ro_conso_combi)   # consonant+vowel combos first
    text = _replace_all(text, ro_specials)        # then standalone vowels/signs
    return text


# -- Text pre-cleaner -----------------------------------------------------------

_BULLET_RE   = re.compile(r"[\u2022\u25cf\u25e6\u2023\u2043\u25aa\u2219\u00b7]")
_ALLOWED_RE  = re.compile(r"[^\u0d80-\u0dff\s.,?!:;'\"()\-\u2014\u200d]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
MAX_CHUNK    = 300


def _clean_text(text):
    text = _BULLET_RE.sub(". ", text)
    text = _ALLOWED_RE.sub("", text)
    text = re.sub(r" {2,}", " ", text).strip()
    return text


def _split_text(text):
    chunks = []
    current = ""
    for sentence in _SENTENCE_RE.split(text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= MAX_CHUNK:
            current = f"{current} {sentence}".strip()
            continue
        if current:
            chunks.append(current)
        if len(sentence) <= MAX_CHUNK:
            current = sentence
            continue
        current = ""
        for word in sentence.split():
            if len(current) + len(word) + 1 <= MAX_CHUNK:
                current = f"{current} {word}".strip()
            else:
                if current:
                    chunks.append(current)
                current = word
    if current:
        chunks.append(current)
    return chunks or [text[:MAX_CHUNK]]


# -- Request schema -------------------------------------------------------------

class SinhalaTTSRequest(BaseModel):
    text: str


# -- Modal class ----------------------------------------------------------------

@app.cls(
    gpu="T4",
    volumes={MODELS_DIR: model_volume},
    scaledown_window=300,
    memory=8192,
)
class SinhalaVITSTTS:

    @modal.enter()
    def load_model(self):
        """Download model weights (once) and load Coqui TTS Synthesizer."""
        import torch
        from huggingface_hub import hf_hub_download

        model_dir = Path(MODELS_DIR)
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path  = model_dir / MODEL_FILE
        config_path = model_dir / CONFIG_FILE

        for filename, dest in [(MODEL_FILE, model_path), (CONFIG_FILE, config_path)]:
            if dest.exists():
                print(f"[SinhalaVITS-M2] Using cached {filename}")
            else:
                print(f"[SinhalaVITS-M2] Downloading {filename} from {MODEL_REPO} ...")
                hf_hub_download(
                    repo_id=MODEL_REPO,
                    filename=filename,
                    local_dir=str(model_dir),
                )
                print(f"[SinhalaVITS-M2] Downloaded {filename} ({dest.stat().st_size // 1024 // 1024} MB)")

        model_volume.commit()

        use_cuda = torch.cuda.is_available()
        print(f"[SinhalaVITS-M2] Loading Synthesizer (cuda={use_cuda}) ...")
        t0 = time.perf_counter()

        from TTS.utils.synthesizer import Synthesizer
        self._synth = Synthesizer(
            tts_checkpoint=str(model_path),
            tts_config_path=str(config_path),
            use_cuda=use_cuda,
        )

        elapsed = time.perf_counter() - t0
        print(f"[SinhalaVITS-M2] Ready in {elapsed:.2f}s (Roshan male voice, {SAMPLE_RATE} Hz)")

    @modal.fastapi_endpoint(method="POST")
    def synthesize(self, req: SinhalaTTSRequest) -> Response:
        """POST /  -- Synthesize Sinhala text to WAV audio.

        Pipeline:
          1. Clean text (strip bullets / non-Sinhala symbols)
          2. Split into sentence-boundary chunks (<= 300 chars each)
          3. Romanize each chunk: Sinhala Unicode -> romanized Latin
          4. VITS synthesis -> numpy waveform per chunk
          5. Concatenate with 200 ms silence gaps -> PCM-16 WAV
        """
        import numpy as np
        import soundfile as sf

        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' cannot be empty.")

        text_clean = _clean_text(text)
        if not text_clean:
            raise HTTPException(
                status_code=422,
                detail="Text contained no Sinhala characters after cleaning.",
            )

        if text_clean != text:
            print(f"[SinhalaVITS-M2] Text cleaned: {len(text)} -> {len(text_clean)} chars")

        chunks = _split_text(text_clean)
        print(f"[SinhalaVITS-M2] Synthesizing {len(text_clean)} chars in {len(chunks)} chunk(s)")

        t0 = time.perf_counter()
        try:
            waveforms = []
            for i, chunk in enumerate(chunks):
                roman = sinhala_to_roman(chunk)
                print(
                    f"[SinhalaVITS-M2] chunk {i+1}/{len(chunks)} "
                    f"({len(chunk)} chars): {chunk[:40]} -> {roman[:40]}"
                )
                wav = self._synth.tts(roman)
                waveforms.append(np.asarray(wav, dtype=np.float32))

            if not waveforms:
                raise HTTPException(status_code=500, detail="No audio chunks generated.")

            silence = np.zeros(int(SAMPLE_RATE * 0.2), dtype=np.float32)
            combined = waveforms[0]
            for wav in waveforms[1:]:
                combined = np.concatenate((combined, silence, wav))

            buf = io.BytesIO()
            sf.write(buf, combined, SAMPLE_RATE, format="WAV", subtype="PCM_16")
            buf.seek(0)
            wav_bytes = buf.getvalue()

            elapsed = time.perf_counter() - t0
            print(
                f"[TIMING] sinhala_vits_m2: {elapsed:.3f}s | "
                f"{len(text_clean)} chars | {len(chunks)} chunks | {len(wav_bytes)} bytes"
            )

            return Response(content=wav_bytes, media_type="audio/wav")

        except HTTPException:
            raise
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"[SinhalaVITS-M2] Error after {elapsed:.2f}s: {exc}")
            raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc
