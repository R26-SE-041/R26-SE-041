"""Maintain a one-question look-ahead buffer while the learner is working."""
import logging

from app.agents.quiz_agent import quiz_agent
from app.graph.graph import get_graph


logger = logging.getLogger(__name__)


def prefetch_next_question(session_id: str) -> None:
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)
    current_state = dict(snapshot.values if snapshot else {})
    # In adaptive mode the next question must not exist until the current
    # question reaches a terminal attempt.  Otherwise a look-ahead question is
    # frozen at the previous difficulty and the quiz only appears adaptive.
    # This applies equally to topic-only and uploaded-resource MCQs.
    if current_state.get("difficulty_mode") == "adaptive":
        return
    # Open-ended difficulty is rubric-score driven and follows the same rule.
    if current_state.get("exam_type") in ("structured", "essay"):
        return
    questions = list(current_state.get("questions", []))
    current_index = int(current_state.get("current_q_index", 0))
    requested = int(current_state.get("num_questions", 0))

    # Keep exactly one item ahead. Never regenerate a question already in the
    # checkpoint, and do nothing once the last question is buffered.
    next_index = current_index + 1
    if next_index >= requested or len(questions) > next_index:
        return
    if len(questions) != next_index:
        return

    generation_state = dict(current_state)
    generation_state["current_q_index"] = next_index
    generated = quiz_agent(generation_state)
    generated_questions = list(generated.get("questions", []))
    if len(generated_questions) <= next_index:
        logger.warning("Question prefetch produced no item | session=%s index=%s", session_id, next_index)
        return

    # The per-session executor prevents answer continuation from racing this
    # merge. Preserve the live current index; only publish the buffered item.
    graph.update_state(config, {
        "questions": generated_questions,
        "quiz_blueprint": generated.get("quiz_blueprint", current_state.get("quiz_blueprint", [])),
        "flagged_questions": generated.get("flagged_questions", current_state.get("flagged_questions", [])),
        "error": generated.get("error"),
        "retry_count": generated.get("retry_count", 0),
        "agent_logs": generated.get("agent_logs", current_state.get("agent_logs", [])),
    })
    logger.info("Question prefetched | session=%s index=%s", session_id, next_index)
