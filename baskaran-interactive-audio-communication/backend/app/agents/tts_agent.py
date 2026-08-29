"""
TTS Agent — LangGraph node (Phase 2).

Responsibility: Convert the localized answer to speech. English uses
Kokoro-82M, Tamil uses Indic Parler-TTS, and Sinhala uses SinhalaVITS.
Stores the audio in Supabase Storage and returns a signed URL.
"""

from app.services.modal_client import call_english_tts, call_sinhala_vits_tts_direct, call_tamil_tts
from app.services.storage import upload_audio
from app.db.supabase import get_supabase
from app.core.logging import get_logger

logger = get_logger(__name__)


async def tts_node(state: dict) -> dict:
    """
    LangGraph node: Text-to-Speech via the language-appropriate TTS model.

    Expected state keys in:
        localized_answer (str): Text to synthesize.
        language (str): Language code for TTS voice selection.
        session_id (str): Used as storage path prefix.

    State keys out:
        audio_url (str | None): Signed Supabase Storage URL of the audio.
    """
    text: str = state.get("localized_answer") or state.get("answer", "")
    language: str = state.get("language", "english")
    session_id: str = state.get("session_id", "unknown")

    if not text:
        return {**state, "audio_url": None}

    logger.info("TTS agent: synthesizing %d chars in %s", len(text), language)

    try:
        if language == "english":
            audio_bytes = await call_english_tts(text)
        elif language == "tamil":
            audio_bytes = await call_tamil_tts(text)
        else:
            audio_bytes = await call_sinhala_vits_tts_direct(text)
        if not audio_bytes:
            raise RuntimeError(f"{language.title()} TTS is unavailable.")
        path = await upload_audio(session_id, audio_bytes)

        # Generate signed URL (1 hour)
        client = await get_supabase()
        result = await client.storage.from_("audio").create_signed_url(path, 3600)
        audio_url = result["signedURL"]
    except RuntimeError as e:
        logger.warning("TTS skipped: %s", e)
        audio_url = None

    return {**state, "audio_url": audio_url}
