"""
Analytics Agent — Computes final analytics report from completed quiz session.
Produces research metrics (grounding score, flagged questions) for paper.
"""
import logging
from app.graph.state import AssessmentState

logger = logging.getLogger(__name__)


def analytics_agent(state: AssessmentState) -> dict:
    """
    Analytics Agent.
    Input:  All state fields (answers, questions, scores, etc.)
    Output: state['final_score'], state['analytics_report']
    """
    logger.info(f"[AnalyticsAgent] Starting | session={state['session_id']}")
    answers   = state.get("answers", [])
    questions = state.get("questions", [])
    logs = list(state.get("agent_logs", []))

    if not answers:
        return {
            "final_score": 0.0,
            "analytics_report": {"message": "No answers recorded."},
            "agent_logs": logs
        }

    # Final score
    total_score = sum(a.get("score", 0.0) for a in answers)
    final_score = round((total_score / len(answers)) * 100, 1)

    # Difficulty progression
    diff_progression = []
    d = state.get("current_difficulty", 0.5)
    for a in answers:
        if a["is_correct"]:
            d = min(1.0, d + 0.1)
        else:
            d = max(0.0, d - 0.1)
        diff_progression.append(round(d, 2))

    # Research metrics
    grounding_scores = [q.get("grounding_score", 0.0) for q in questions]
    avg_grounding = (
        sum(grounding_scores) / len(grounding_scores)
        if grounding_scores else 0.0
    )
    flagged_count = len(state.get("flagged_questions", []))
    flagged_pct   = round(flagged_count / max(len(questions), 1) * 100, 1)

    # Performance metrics
    avg_attempts   = sum(a.get("attempts", 1) for a in answers) / len(answers)
    avg_hints      = sum(a.get("hints_used", 0) for a in answers) / len(answers)
    total_time_sec = sum(a.get("time_taken_sec", 0) for a in answers)

    report = {
        "final_score":            final_score,
        "total_questions":        len(questions),
        "total_answered":         len(answers),
        "topic_scores":           state.get("topic_scores", {}),
        "bloom_scores":           state.get("bloom_scores", {}),
        "difficulty_progression": diff_progression,
        "avg_attempts":           round(avg_attempts, 2),
        "avg_hints_used":         round(avg_hints, 2),
        "total_time_sec":         total_time_sec,
        "total_time_min":         round(total_time_sec / 60, 1),
        "weak_topics":            state.get("weak_topics", []),
        "strong_topics":          state.get("strong_topics", []),
        "recommendations":        state.get("recommendations", []),
        # Research metrics (put in paper!)
        "avg_grounding_score":    round(avg_grounding, 3),
        "flagged_questions_count": flagged_count,
        "flagged_questions_pct":   flagged_pct,
        "agent_logs":             logs
    }

    logs.append(f"[AnalyticsAgent] Final score={final_score}% | grounding={avg_grounding:.3f} | flagged={flagged_pct}%")
    logger.info(f"[AnalyticsAgent] Done | score={final_score}%")

    return {
        "final_score":      final_score,
        "analytics_report": report,
        "agent_logs":       logs
    }
