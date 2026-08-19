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

    # ── Delta calculation ──────────────────────────
    delta = 0.0

    if last["is_correct"]:
        if last["attempts"] == 1 and last.get("hints_used", 0) == 0:
            delta = +0.10   # Perfect answer
        elif last["attempts"] == 1:
            delta = +0.07   # Correct on first try but used hints
        else:
            delta = +0.04   # Correct after retries
    else:
        if last.get("hints_used", 0) >= 2:
            delta = -0.15   # Struggled significantly
        else:
            delta = -0.10   # Simply wrong

    # Speed modifier (correct + fast = more confident → increase more)
    if last["is_correct"] and len(answers) > 2:
        avg_time = sum(a["time_taken_sec"] for a in answers[:-1]) / (len(answers) - 1)
        if avg_time > 0 and last["time_taken_sec"] < avg_time * 0.7:
            delta *= 1.2    # 20% bonus for quick correct answer

    # Clamp delta to avoid too-fast changes
    delta = max(-0.20, min(0.20, delta))
    new_d = max(0.0, min(1.0, d + delta))

    logs.append(f"[AdaptiveAgent] Difficulty: {old_d:.2f} → {new_d:.2f} (Δ={delta:+.2f}) | "
                f"correct={last['is_correct']} | attempts={last['attempts']} | hints={last.get('hints_used',0)}")
    logger.info(f"[AdaptiveAgent] Difficulty updated: {old_d:.2f} → {new_d:.2f}")

    return {
        "current_difficulty": new_d,
        "agent_logs": logs
    }
