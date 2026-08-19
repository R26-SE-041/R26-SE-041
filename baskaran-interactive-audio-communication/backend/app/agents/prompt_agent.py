"""
Transcript Correction Agent -- LangGraph node (Phase 2).

Responsibility: Correct obvious ASR errors in the raw transcript while
preserving the speaker's original meaning exactly. Uses Gemma 4 12B IT
on Modal (reuses the RAG deployment -- no extra container).
"""

from app.services.modal_client import call_transcript_corrector
from app.core.logging import get_logger

logger = get_logger(__name__)


async def prompt_agent_node(state: dict) -> dict:
    """
    LangGraph node: Transcript correction via Gemma 4 12B IT.

    Expected state keys in:
        transcript (str): Raw transcript from STT.
        language (str): Target language mode.

    State keys out:
        corrected_transcript (str): ASR-corrected transcript (intent preserved).
    """
    transcript: str = state.get("transcript", "")
    language: str = state.get("language", "english")

    logger.info("Transcript correction agent: correcting %d chars", len(transcript))

    result = await call_transcript_corrector(transcript, language)

    return {
        **state,
        "corrected_transcript": result.get("corrected_transcript", transcript),
    }
