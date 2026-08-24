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
        return {"agent_logs": logs}

    last = answers[-1]
    d = state.get("current_difficulty", 0.5)
    old_d = d

    # Skip if we shouldn't adapt (not adaptive mode and not the first question)
    if state.get("difficulty_mode") != "adaptive" and len(answers) > 1:
        return {"agent_logs": logs}

    # ── Attempt-based difficulty logic ──────────────────────────
    attempts = last.get("attempts", 1)
    
    if attempts == 1:
        new_d = 0.8  # Hard
        level_name = "Hard"
    elif attempts in [2, 3]:
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
        "agent_logs": logs
    }
