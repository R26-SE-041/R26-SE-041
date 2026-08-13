"""
LangGraph StateGraph Definition.
Builds and compiles the multi-agent assessment workflow.
"""
import logging
import os
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AssessmentState
from app.agents.ingestion_agent import ingestion_agent
from app.agents.knowledge_agent import knowledge_agent
from app.agents.quiz_agent import quiz_agent
from app.agents.evaluation_agent import evaluation_agent
from app.agents.adaptive_agent import adaptive_agent
from app.agents.recommendation_agent import recommendation_agent
from app.agents.analytics_agent import analytics_agent
from app.agents.error_handler import error_handler_node

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("SQLITE_DB_PATH", "./db/sessions.db")


def route_after_ingestion(state: AssessmentState) -> str:
    """After ingestion: go to knowledge or error handler."""
    if state.get("error") or state.get("ingestion_status") == "error":
        return "error_handler"
    return "knowledge"


def route_after_knowledge(state: AssessmentState) -> str:
    """After knowledge: go to quiz or error handler."""
    if state.get("error") or state.get("knowledge_status") == "error":
        return "error_handler"
    return "quiz_generate"


def route_after_quiz(state: AssessmentState) -> str:
    """After quiz_agent: go to evaluation or error handler."""
    if state.get("error"):
        return "error_handler"
    # If there's a pending answer, evaluate it
    if state.get("_pending_answer"):
        return "evaluation"
    # No pending answer yet — wait (API will inject answer)
    return END


def route_after_evaluation(state: AssessmentState) -> str:
    """After evaluation: continue quiz loop or finish."""
    if state.get("error"):
        return "error_handler"
    answered = len(state.get("answers", []))
    total = len(state.get("questions", []))
    # Check if current question can be retried
    last_answer = state["answers"][-1] if state.get("answers") else None
    if last_answer and not last_answer["is_correct"] and last_answer["attempts"] < 3:
        return "quiz_generate"  # Same question, retry with hint
    if answered < state.get("num_questions", 0):
        return "adaptive"       # Move to next question
    return "recommendation"     # All questions done


def route_after_error(state: AssessmentState) -> str:
    """After error handler: retry or go to analytics."""
    if state.get("retry_count", 0) >= 3:
        return "analytics"  # Give up — produce partial results
    return "quiz_generate"  # Retry


def build_graph() -> any:
    """
    Build and compile the LangGraph StateGraph.
    Returns a compiled graph with SQLite checkpointing.
    """
    builder = StateGraph(AssessmentState)

    # ── Register all agent nodes ───────────────────
    builder.add_node("ingestion",       ingestion_agent)
    builder.add_node("knowledge",       knowledge_agent)
    builder.add_node("quiz_generate",   quiz_agent)
    builder.add_node("evaluation",      evaluation_agent)
    builder.add_node("adaptive",        adaptive_agent)
    builder.add_node("recommendation",  recommendation_agent)
    builder.add_node("analytics",       analytics_agent)
    builder.add_node("error_handler",   error_handler_node)

    # ── Define edges ───────────────────────────────
    builder.set_entry_point("ingestion")

    # Linear setup phase — with error routing
    builder.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {"knowledge": "knowledge", "error_handler": "error_handler"}
    )
    builder.add_conditional_edges(
        "knowledge",
        route_after_knowledge,
        {"quiz_generate": "quiz_generate", "error_handler": "error_handler"}
    )

    # Quiz generate → evaluation or wait
    builder.add_conditional_edges(
        "quiz_generate",
        route_after_quiz,
        {"evaluation": "evaluation", "error_handler": "error_handler", END: END}
    )

    # Evaluation → adaptive or finish
    builder.add_conditional_edges(
        "evaluation",
        route_after_evaluation,
        {
            "adaptive": "adaptive",
            "quiz_generate": "quiz_generate",
            "recommendation": "recommendation",
            "error_handler": "error_handler"
        }
    )

    # Adaptive → next question
    builder.add_edge("adaptive", "quiz_generate")

    # End phase
    builder.add_edge("recommendation", "analytics")
    builder.add_edge("analytics", END)

    # Error recovery
    builder.add_conditional_edges(
        "error_handler",
        route_after_error,
        {"quiz_generate": "quiz_generate", "analytics": "analytics"}
    )

    # ── Compile with SQLite checkpointer ──────────
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)

    logger.info("LangGraph compiled successfully")
    return graph


# Singleton — compiled once at startup
_graph = None


def get_graph():
    """Return the compiled graph (singleton)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
