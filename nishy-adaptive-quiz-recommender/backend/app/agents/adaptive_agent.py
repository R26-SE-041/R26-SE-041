"""
Adaptive Agent — Updates difficulty level based on student performance.
Implements simplified IRT-inspired adaptive algorithm.
"""
import logging
from app.graph.state import AssessmentState

logger = logging.getLogger(__name__)


def adaptive_agent(state: AssessmentState) -> dict:
    """
    Adaptive Agent.
    Input:  state['answers'], state['current_difficulty']
    Output: state['current_difficulty'] (updated)
    """
    logger.info(f"[AdaptiveAgent] Starting | session={state['session_id']}")
    answers = state.get("answers", [])
    logs = list(state.get("agent_logs", []))

    if not answers:
        return {"_skip_requested": False, "agent_logs": logs}

    last = answers[-1]
    d = state.get("current_difficulty", 0.5)
    old_d = d

    # Fixed modes must never be silently changed after an answer.
    if state.get("difficulty_mode") != "adaptive":
        return {"_skip_requested": False, "agent_logs": logs}

    questions = state.get("questions", [])
    answered_question = next((q for q in questions if q.get("q_id") == last.get("q_id")), None)
    q_type = answered_question.get("q_type", "mcq") if answered_question else "mcq"

    if q_type in ("structured", "essay"):
        # These are graded holistically in one shot — there is no hint/retry
        # mechanic, so "attempts" is always 1. The attempts-based logic below
        # would read that as "got it right away" and pin difficulty at Hard
        # forever, no matter how low the student actually scored. Use the
        # graded score instead so difficulty genuinely adapts for these types.
        score = float(last.get("score", 0.0))
        if score >= 0.7:
            new_d, level_name = 0.8, "Hard"
        elif score >= 0.4:
            new_d, level_name = 0.5, "Medium"
        else:
            new_d, level_name = 0.2, "Easy"
        logs.append(
            f"[AdaptiveAgent] Difficulty updated based on {q_type} score {score:.2f}: "
            f"{old_d:.2f} → {new_d:.2f} ({level_name})"
        )
        logger.info(f"[AdaptiveAgent] Difficulty updated: {old_d:.2f} → {new_d:.2f} ({level_name})")
        return {"current_difficulty": new_d, "_skip_requested": False, "agent_logs": logs}

    # ── Attempt-based difficulty logic (MCQ / fill_blank) ──────────────
    attempts = last.get("attempts", 1)
    
    if attempts <= 2:
        new_d = 0.8  # Hard
        level_name = "Hard"
    elif attempts == 3:
        new_d = 0.5  # Medium
        level_name = "Medium"
    else:
        new_d = 0.2  # Easy
        level_name = "Easy"

    logs.append(f"[AdaptiveAgent] Difficulty updated based on {attempts} attempt(s): {old_d:.2f} → {new_d:.2f} ({level_name}) | "
                f"correct={last['is_correct']}")
    logger.info(f"[AdaptiveAgent] Difficulty updated: {old_d:.2f} → {new_d:.2f} ({level_name})")

    return {
        "current_difficulty": new_d,
        "_skip_requested": False,
        "agent_logs": logs
    }
