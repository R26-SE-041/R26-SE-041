"""
Central application configuration.
All values are loaded from environment variables via pydantic-settings.
Never hardcode secrets — use .env or platform secrets.
"""

from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "VoiceLearn AI"
    app_version: str = "0.1.0"
    debug: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        """Accept common hosting values such as DEBUG=release without crashing."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value

    # ── Supabase ─────────────────────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    # This is intentionally a new collection name.  The previous `documents`
    # collection contains 384-dimensional MiniLM embeddings and must never be
    # queried alongside BGE-M3's 1024-dimensional vectors.
    chroma_collection: str = "documents_bge_m3"

    # ── Modal endpoints (set after `modal deploy`) ───────────────────────────
    modal_whisper_url: str = ""
    modal_indic_stt_url: str = ""         # lemuralabs/tamil-asr-qwen3 (osmapi/tamil-asr-qwen3) — Tamil-native STT
    modal_transcript_corrector_url: str = ""  # Gemma 4 12B — ASR transcript correction
    modal_rag_generator_url: str = ""
    modal_localizer_url: str = ""
    modal_tts_url: str = ""
    # ── Tamil-only TTS (AI4Bharat Indic Parler-TTS on Modal A10G) ─────────────
    # Set USE_TAMIL_TTS=true AFTER deploying backend/modal_endpoints/tamil_parler_tts.py
    # and filling MODAL_TAMIL_TTS_URL.  When false, Tamil answers show text only.
    use_tamil_tts: bool = False
    modal_tamil_tts_url: str = ""
    # Deprecated — Qwen2.5-3B prompt enhancer removed; kept so old .env files don't crash
    modal_prompt_enhancer_url: str = ""

    # ── Temporary Tamil TTS Test (isolated from production RAG pipeline) ───────
    # Controls POST /api/v1/test/tamil-tts and has NO effect on use_tamil_tts.
    # Set USE_TAMIL_TTS_TEST=true to enable the test route.
    # Set USE_TAMIL_TTS_TEST=false (default) to disable/hide it completely.
    # The modal_tamil_tts_url field above is shared — no separate URL needed.
    # REMOVE this setting after TTS testing is complete.
    use_tamil_tts_test: bool = False

    # ── English TTS (Parler-TTS Mini v1 on Modal T4) ──────────────────────────
    # Set USE_ENGLISH_TTS=true AFTER deploying backend/modal_endpoints/english_parler_tts.py
    # and filling MODAL_ENGLISH_TTS_URL.  When false, English answers show text only.
    use_english_tts: bool = False
    modal_english_tts_url: str = ""
    # Default Parler-TTS style description — controls voice gender, pace, tone.
    # Override per-request by passing a 'description' field to the endpoint.
    english_tts_default_description: str = (
        "A clear, warm English speaker with a calm educational tone, "
        "moderate speaking speed, natural pauses, confident delivery, "
        "and clean studio-quality audio."
    )
    # Used only by the mixed Tamil + English orchestrator. Pure English keeps
    # the default description above, while mixed English is aligned to the
    # supplied IndicF5 Tamil female prompt.
    mixed_english_tts_description: str = (
        "A clear, warm adult female English speaker with a soft, natural voice, "
        "moderate pitch, calm conversational delivery, moderate speaking speed, "
        "gentle energy, natural pauses, and clean studio-quality audio."
    )

    # ── Temporary English TTS Test (isolated from production RAG pipeline) ──────
    # Controls POST /api/v1/test/english-tts.  Has NO effect on use_english_tts.
    # Set USE_ENGLISH_TTS_TEST=true to enable the test route.
    # REMOVE this setting after English TTS testing is complete.
    use_english_tts_test: bool = False

    # ── Mixed TTS (Tamil + English code-switched answers) ─────────────────────
    # Set USE_MIXED_TTS=true to enable automatic mixed-answer TTS routing.
    # Pure Tamil and pure English routing are NOT affected when this is false.
    # When true, a Tamil-mode answer that contains both scripts is routed through
    # the mixed orchestrator (IndicF5 for Tamil parts, Parler-TTS for English).
    use_mixed_tts: bool = False
    # Controls POST /api/v1/test/mixed-tts.  Independent of use_mixed_tts.
    # Set USE_MIXED_TTS_TEST=true to enable the temporary mixed TTS test route.
    # REMOVE this setting after mixed TTS testing is complete.
    use_mixed_tts_test: bool = False

    # ── Mode C — Multilingual Single-Model TTS experiment (ISOLATED, DEV ONLY) ─────
    # Controls POST /api/v1/test/multilingual-tts.
    # Mode C sends the ORIGINAL Tamil+English mixed text directly to IndicF5
    # with NO pre-processing: no transliteration, no segmentation, no Mode A/B logic.
    # Completely independent of use_mixed_tts, use_mixed_tts_test, and all production routing.
    # Set USE_MULTILINGUAL_TTS_TEST=true to enable.
    # MODAL_TAMIL_TTS_URL is reused — no separate URL needed (same IndicF5 endpoint).
    # REMOVE this setting after Mode C evaluation is complete.
    use_multilingual_tts_test: bool = False

    # ── Mode D — Indic Parler Mixed TTS experiment (ISOLATED, DEV ONLY) ──────────
    # Controls POST /api/v1/test/indic-parler-mixed-tts.
    # Mode D sends the ORIGINAL Tamil+English mixed text directly to the NEW
    # ai4bharat/indic-parler-tts model in ONE call — a unified multilingual model
    # that handles Tamil+English code-switching in a single inference pass.
    #
    # Architecture: completely separate from ALL existing TTS services:
    #   - Does NOT use IndicF5 (Mode A, Mode B, Mode C, Tamil TTS production)
    #   - Does NOT use Parler-TTS Mini v1 (English TTS production)
    #   - Has its own Modal app: voicelearn-indic-parler-mixed-tts
    #   - Has its own URL: MODAL_INDIC_PARLER_MIXED_TTS_URL
    #
    # Set USE_INDIC_PARLER_MIXED_TTS_TEST=true AFTER deploying
    # backend/modal_endpoints/indic_parler_mixed_tts.py
    # and filling MODAL_INDIC_PARLER_MIXED_TTS_URL in .env.
    #
    # REMOVE this setting after Mode D evaluation is complete.
    use_indic_parler_mixed_tts_test: bool = False
    modal_indic_parler_mixed_tts_url: str = ""

    # ── Modal BGE Retrieval Models ─────────────────────────────────────────────
    # Set USE_MODAL_RETRIEVAL_MODELS=true after deploying bge_retrieval.py to
    # route BGE-M3 embedding and cross-encoder reranking to Modal GPU instead
    # of the local CPU.  When false, the existing local model path is used
    # unchanged — safe for side-by-side latency comparison.
    use_modal_retrieval_models: bool = False
    modal_bge_embed_url: str = ""   # BGEEmbedder /embed endpoint (set after modal deploy)
    modal_bge_rerank_url: str = ""  # BGEReranker /rerank endpoint (set after modal deploy)

    # ── Modal auth token ─────────────────────────────────────────────────────
    modal_token_id: str = ""
    modal_token_secret: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── File upload limits ────────────────────────────────────────────────────
    max_upload_mb: int = 50
    # A bounded request lifecycle prevents a stalled model load or vector-store
    # operation from leaving a browser upload pending forever.
    document_ingestion_timeout_seconds: int = 300
    supabase_request_timeout_seconds: int = 10
    # Temporary filesystem fallback until Supabase Storage is configured.
    local_document_store_path: str = "local_documents"

    # ── TEMPORARY Sinhala TTS Test (dialoglk/SinhalaVITS-TTS-F1, DEV ONLY) ────
    # Controls POST /api/v1/test/sinhala-tts and POST /api/v1/test/sinhala-tts/romanize.
    # Has NO effect on Tamil TTS, English TTS, Mixed TTS, ASR, RAG, or any
    # production route — completely isolated.
    #
    # Steps to enable:
    #   1. modal deploy backend/modal_endpoints/sinhala_vits_tts.py
    #   2. Copy the printed URL into MODAL_SINHALA_VITS_TTS_URL below.
    #   3. Set USE_SINHALA_TTS_TEST=true and restart the backend.
    #
    # Set false to disable the test routes without removing any code.
    # REMOVE this setting after Sinhala TTS evaluation is complete.
    use_sinhala_tts_test: bool = False
    modal_sinhala_vits_tts_url: str = ""
    # Separate URL for the /romanize debug endpoint — Modal assigns each
    # @fastapi_endpoint-decorated method its own independent URL.
    modal_sinhala_vits_tts_romanize_url: str = ""
    # Same existing Gemma deployment, dedicated endpoint method for the isolated
    # Sinhala mixed-TTS experiment.  It is never used by RAG or ASR flows.
    modal_sinhala_phonetics_url: str = ""
    sinhala_phonetics_cache_path: str = "data/sinhala_tts_phonetics.sqlite3"

    # ── TEMPORARY Sinhala ASR Test (Lingalingeswaran/whisper-small-sinhala, DEV ONLY) ─
    # Controls POST /api/v1/test/sinhala-asr.
    # Completely isolated from Tamil ASR, English ASR, RAG, TTS, and all other routes.
    #
    # Steps to enable:
    #   1. modal deploy backend/modal_endpoints/sinhala_whisper_asr.py
    #   2. Copy the printed URL into MODAL_SINHALA_ASR_URL below.
    #   3. Set USE_SINHALA_ASR_TEST=true and restart the backend.
    #
    # Set false to disable the test route without removing any code.
    # REMOVE this setting after Sinhala ASR evaluation is complete.
    use_sinhala_asr_test: bool = False
    modal_sinhala_asr_url: str = ""

    # Temporary manual Sinhala transcript -> existing multilingual RAG test.
    # This flag does not affect production RAG, ASR, or any TTS route.
    use_sinhala_rag_test: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
