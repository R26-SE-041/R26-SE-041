"""
Modal Serverless Endpoint: Whisper Large V3 — Speech-to-Text (Auto-detect + Native Script)

Key design:
  The UI "language" selector controls the RESPONSE language (what language the RAG answer
  comes back in). It does NOT restrict what language the user can SPEAK.

  This endpoint auto-detects the actual spoken language from the audio, then:
    • Tamil / Sinhala detected → suppress all ASCII word tokens so the decoder
      MUST emit native Unicode characters (not English words like "Night" for "நாய்")
    • English / other → standard Whisper transcription (no suppression)

  If the user explicitly selected Tamil/Sinhala in the UI, we honour that
  (trust user intent over Whisper's auto-detection, in case auto-detect fails
  on short audio clips).

Two-phase strategy:
  Phase 1 — eager language detection (fast, no token generation, language=None).
             faster-whisper computes this eagerly when transcribe() is called,
             so info.language is available BEFORE iterating the segment generator.
  Phase 2 — full transcription using the detected/forced language + suppress list.

Deploy:
    modal deploy backend/modal_endpoints/whisper_stt.py
"""

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
        "faster-whisper==1.1.0",
        "huggingface_hub==0.26.2",
        "fastapi[standard]==0.115.0",
        "nvidia-cublas-cu12",
    )
)

app = modal.App("voicelearn-whisper-stt", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

# User language-hint → ISO language code
# ALL explicit selections are now strictly enforced — only 'mixed' auto-detects.
LANG_MAP = {
    "english": "en",
    "tamil":   "ta",
    "sinhala": "si",
    "mixed":   None,   # auto-detect only in mixed mode
}

# Languages that are explicitly forced (not auto-detected)
_EXPLICIT_FORCE_LANGS = {"english", "tamil", "sinhala"}

# Rich native-script initial prompts — seed the Whisper decoder with Tamil/Sinhala
# text so beam search starts in the right Unicode range.
INITIAL_PROMPT_MAP = {
    "en": None,
    "ta": (
        "இது தமிழ் கல்வி உரை. மாணவர் தமிழில் கேட்கிறார்: "
        "நாய், பூனை, மனிதன், விலங்கு, உணவு, பிரியாணி, "
        "கேள்வி, விடை, தமிழ் மொழி."
    ),
    "si": (
        "මෙය සිංහල අධ්‍යාපන කතාවකි. "
        "ප්‍රශ්නය සිංහලෙන්: ආහාර, ශිෂ්‍ය, ප්‍රශ්නය."
    ),
    None: None,
}

# ISO codes that require native-script enforcement (suppress ASCII tokens)
_NATIVE_SCRIPT_LANGS = {"ta", "si"}


@app.cls(
    gpu="T4",
    volumes={"/models": model_volume},
    scaledown_window=300,
    memory=4096,
)
class WhisperSTT:

    @modal.enter()
    def load_model(self):
        """
        Load Whisper Large V3 and build the ASCII-word suppress list.

        For each token in the vocabulary, decode it to actual text.
        Tokens that decode to purely ASCII alphabetic strings (English words/subwords)
        are collected into self.ascii_suppress_ids.  This list is passed to
        suppress_tokens for Tamil/Sinhala transcription, blocking English output.
        """
        from faster_whisper import WhisperModel
        from faster_whisper.tokenizer import Tokenizer as FWTokenizer

        self.model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16",
            download_root="/models",
        )

        # Build suppress list via decode() — iterate every token, decode to text,
        # then check if the clean text is purely ASCII alphabetic (English word/subword).
        #
        # CRITICAL: Whisper's BPE tokenizer prepends "Ġ" (U+0120) to word-starting
        # tokens (e.g. "Ġeat", "Ġnight", "Ġbiryani"). Without stripping this
        # character first, decoded.isascii() returns False and the token is missed —
        # allowing Whisper to still output English words even with suppress_tokens set.
        fw_tok = FWTokenizer(
            self.model.hf_tokenizer,
            multilingual=True,
            task="transcribe",
            language="ta",
        )
        vocab_size = self.model.hf_tokenizer.get_vocab_size()

        self.ascii_suppress_ids: list[int] = []
        for tid in range(min(vocab_size, 50_260)):
            try:
                decoded = fw_tok.decode([tid])
                # Strip BPE word-boundary prefix characters before ASCII check:
                #   Ġ (U+0120) — GPT-2 / Whisper BPE space prefix
                #   ▁ (U+2581) — SentencePiece space prefix
                #   Ċ (U+010A) — newline byte in GPT-2 BPE
                clean = decoded.replace("\u0120", "").replace("\u2581", "").replace("\u010a", "")
                # Suppress purely ASCII alphabetic tokens (English words & subwords).
                # Includes single-letter tokens so Whisper can't spell out words
                # character-by-character either.
                if clean and clean.isascii() and clean.isalpha():
                    self.ascii_suppress_ids.append(tid)
            except Exception:
                pass

        print(
            f"[WhisperSTT] Ready. ASCII suppress list: "
            f"{len(self.ascii_suppress_ids)} tokens "
            f"(applied for Tamil/Sinhala to block English output)."
        )

    # ── internal helpers ──────────────────────────────────────────────────────

    def _detect_language(self, tmp_path: str) -> str:
        """
        Quick language detection using faster-whisper.

        faster-whisper computes language detection EAGERLY when transcribe() is
        called (before any segment tokens are generated).  We discard the lazy
        segment generator and only use info.language.
        """
        _lazy_segs, detect_info = self.model.transcribe(
            tmp_path,
            language=None,      # auto-detect
            task="transcribe",
            beam_size=1,        # greedy — fast, we only need the language tag
            vad_filter=True,
            suppress_tokens=[-1],
            condition_on_previous_text=False,
        )
        # info.language is set eagerly; no need to iterate _lazy_segs
        return detect_info.language   # ISO code e.g. "ta", "si", "en"

    def _transcribe_with_suppress(
        self,
        tmp_path: str,
        iso_lang: str,
    ) -> tuple[str, str]:
        """
        Transcribe audio forcing native-script output for Tamil/Sinhala.
        Returns (transcript, detected_iso_lang).
        """
        apply_suppress = iso_lang in _NATIVE_SCRIPT_LANGS
        suppress_tokens = self.ascii_suppress_ids if apply_suppress else [-1]
        initial_prompt  = INITIAL_PROMPT_MAP.get(iso_lang)

        segments, info = self.model.transcribe(
            tmp_path,
            language=iso_lang,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            suppress_tokens=suppress_tokens,
        )
        transcript = " ".join(seg.text for seg in segments).strip()
        return transcript, info.language

    # ── endpoint ──────────────────────────────────────────────────────────────

    @modal.fastapi_endpoint(method="POST")
    async def transcribe(
        self,
        audio_file: "UploadFile",
        # Multipart fields must use Form. Otherwise FastAPI reads this as a
        # query parameter and silently falls back to "english".
        language_hint: str = Form("english"),
    ):
        """
        Transcribe audio with automatic language detection.

        Logic:
          1. If user explicitly selected Tamil or Sinhala → trust that choice.
          2. Otherwise (English / Mixed) → auto-detect the spoken language.
          3. If Tamil or Sinhala is active → suppress ASCII tokens to force
             native Unicode output (prevents "Night" for "நாய்").
        """
        if audio_file is None:
            return JSONResponse({"error": "audio_file is required"}, status_code=400)

        audio_bytes = await audio_file.read()
        if not audio_bytes:
            return JSONResponse({"error": "audio_file is empty"}, status_code=400)

        lang_hint = language_hint.lower()
        start = time.perf_counter()

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # ── Step 1: Determine effective ISO language ──────────────────────────
        if lang_hint in _EXPLICIT_FORCE_LANGS:
            # User explicitly chose English / Tamil / Sinhala — strictly force it.
            # NO auto-detection: English mode = only English, Tamil = only Tamil.
            effective_iso = LANG_MAP[lang_hint]   # "en", "ta", or "si"
            print(f"[WhisperSTT] Strict mode: forcing language={effective_iso} (hint={lang_hint})")
        else:
            # Mixed mode only — auto-detect the spoken language.
            effective_iso = self._detect_language(tmp_path)
            print(f"[WhisperSTT] Mixed/auto-detect: detected language={effective_iso}")

        # ── Step 2: Transcribe with appropriate suppress list ─────────────────
        transcript, detected_iso = self._transcribe_with_suppress(tmp_path, effective_iso)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return {
            "transcript":        transcript,
            "detected_language": detected_iso,
            "duration_ms":       elapsed_ms,
        }


@app.local_entrypoint()
def test():
    print("Whisper STT endpoint ready. Use 'modal deploy' to publish.")
