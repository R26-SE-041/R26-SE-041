"""
Localization Agent — LangGraph node (Phase 2).

Responsibility: Format/translate the generated answer into the
user's chosen language using Qwen2.5-7B on Modal.
Supports: English, Tamil, and Sinhala.
"""

from app.services.modal_client import call_localizer
from app.core.logging import get_logger

logger = get_logger(__name__)


async def localization_node(state: dict) -> dict:
    """
    LangGraph node: Answer localization/translation.

    Expected state keys in:
        answer (str): Raw English answer from RAG agent.
        language (str): Target language mode.

    State keys out:
        localized_answer (str): Answer in the target language.
    """
    answer: str = state.get("answer", "")
    language: str = state.get("language", "english")

    logger.info("Localization agent: target language=%s", language)

    if language == "english":
        # No translation needed — fast passthrough
        return {**state, "localized_answer": answer}

    try:
        result = await call_localizer(answer, language)
        localized = result.get("localized_text", answer)
        logger.info(
            "Localization done: %d chars → %d chars (lang=%s)",
            len(answer),
            len(localized),
            language,
        )
    except Exception as exc:
        # Graceful fallback — never crash the pipeline
        logger.warning(
            "Localization agent failed (%s): %s — falling back to English answer",
            type(exc).__name__,
            exc,
        )
        localized = answer

    return {
        **state,
        "localized_answer": localized,
    }
