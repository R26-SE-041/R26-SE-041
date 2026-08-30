"""
Error Handler Node — Graceful recovery for LangGraph errors.
"""
import logging
from app.graph.state import AssessmentState

logger = logging.getLogger(__name__)

# Errors that cannot be fixed by retrying quiz generation
FATAL_ERRORS = [
    "No content could be extracted",
    "ChromaDB storage failed",
    "Knowledge extraction LLM call failed",
    "Fewer than 2 topics detected",
    "No chunks available",
    "Cannot connect to Modal endpoint",
    "Question generation service unavailable",
    "Insufficient source context to generate a valid question.",
]


def error_handler_node(state: AssessmentState) -> dict:
    """
    Called when any agent sets state['error'].
    Attempts graceful recovery up to 3 retries.
    After max retries or fatal errors: clears error and routes to analytics.
    """
    error = state.get("error", "Unknown error")
    retry_count = state.get("retry_count", 0)
    logs = list(state.get("agent_logs", []))

    log_msg = f"[ErrorHandler] Error: {error} | Retry count: {retry_count}"
    logger.warning(log_msg)
    logs.append(log_msg)

    # Check if this is a fatal error — skip retry by setting retry_count to max
    is_fatal = any(keyword in str(error) for keyword in FATAL_ERRORS)
    if is_fatal:
        logger.error(f"[ErrorHandler] Fatal error detected, skipping retry: {error}")
        retry_count = 3  # Force analytics path

    next_retry_count = retry_count + 1
    return {
        # Preserve an exhausted error so it cannot be mistaken for completion.
        "error":       error if is_fatal or next_retry_count >= 3 else None,
        "retry_count": next_retry_count,
        "agent_logs":  logs
    }
