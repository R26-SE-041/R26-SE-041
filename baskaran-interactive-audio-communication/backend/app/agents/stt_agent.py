"""
STT Agent — LangGraph node.

Responsibility: Route audio to the language-appropriate Modal ASR endpoint and
populate the transcript in the pipeline state. Sinhala uses the dedicated
whisper-small-sinhala model; Tamil can use Qwen3 ASR; other modes use Whisper
Large V3.

Single Responsibility: this node ONLY handles speech-to-text.
"""

from app.services.modal_client import call_whisper
from app.core.logging import get_logger

logger = get_logger(__name__)


async def stt_node(state: dict) -> dict:
    """
    LangGraph node: language-routed Speech-to-Text on Modal.

    Expected state keys in:
        audio_bytes (bytes): Raw audio data.
        audio_filename (str): Original filename.
        language (str): User-selected language mode.

    State keys out:
        transcript (str): Whisper transcription.
        detected_language (str): ISO language code returned by Whisper.
        duration_ms (int): Audio duration.
    """
    audio_bytes: bytes = state["audio_bytes"]
    filename: str = state.get("audio_filename", "recording.webm")
    language: str = state.get("language", "english")

    logger.info("STT node: processing %d bytes, language=%s", len(audio_bytes), language)

    result = await call_whisper(audio_bytes, filename, language)

    return {
        **state,
        "transcript": result["transcript"],
        "detected_language": result.get("detected_language", "en"),
        "duration_ms": result.get("duration_ms", 0),
    }
