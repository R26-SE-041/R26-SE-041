"""Central application configuration loaded from environment variables."""

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

    app_name: str = "VoiceLearn AI"
    app_version: str = "1.0.0"
    debug: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "documents_bge_m3"

    # Final ASR, RAG, localization, and transcript-correction services.
    modal_whisper_url: str = ""
    modal_indic_stt_url: str = ""
    modal_sinhala_asr_url: str = ""
    modal_transcript_corrector_url: str = ""
    modal_rag_generator_url: str = ""
    # Dedicated answer-generation services.  Keep these separate from the
    # transcript corrector endpoint, which is intentionally unchanged.
    modal_base_gemma_url: str = ""
    modal_finetuned_gemma_v2_url: str = ""
    modal_localizer_url: str = ""
    # Temporary latency experiment. Set false to restore Gemma English -> Localizer.
    use_direct_multilingual_gemma: bool = True
    modal_prompt_enhancer_url: str = ""  # Backward-compatible environment key.

    # Final language-specific TTS services.
    use_english_tts: bool = False
    modal_english_kokoro_tts_url: str = ""
    # Legacy Parler URL; retained only so older .env files remain loadable.
    modal_english_tts_url: str = ""
    english_tts_voice: str = "af_heart"
    english_tts_speed: float = 1.0
    use_tamil_tts: bool = False
    # ai4bharat/indic-parler-tts endpoint, promoted from the completed evaluation.
    modal_indic_parler_mixed_tts_url: str = ""
    # Retained so existing environments remain loadable; not used by final routing.
    modal_tamil_tts_url: str = ""
    modal_sinhala_vits_tts_url: str = ""

    # Compatibility-only endpoints are not registered by the final API.
    modal_sinhala_vits_tts_romanize_url: str = ""
    modal_sinhala_phonetics_url: str = ""

    # Legacy generic TTS URL retained for compatibility outside the final UI.
    modal_tts_url: str = ""

    use_modal_retrieval_models: bool = False
    modal_bge_embed_url: str = ""
    modal_bge_rerank_url: str = ""

    modal_token_id: str = ""
    modal_token_secret: str = ""

    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ]
    max_upload_mb: int = 50
    document_ingestion_timeout_seconds: int = 300
    supabase_request_timeout_seconds: int = 10
    local_document_store_path: str = "local_documents"
    local_history_store_path: str = "local_history"


@lru_cache
def get_settings() -> Settings:
    return Settings()
