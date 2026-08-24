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

    ATTEMPT_MARKS = {1: 100, 2: 75, 3: 50, 4: 25}

    weighted_scores = []
    question_marks_detail = []

    for i, a in enumerate(answers):
        attempt = a.get("attempts", 1)
        is_correct = a.get("is_correct", False)
        pts = ATTEMPT_MARKS.get(attempt, 25) if is_correct else 0
        weighted_scores.append(pts)

        # Find matching question for topic/bloom/difficulty
        q_id = a.get("q_id", "")
        q_obj = next((q for q in questions if q.get("q_id") == q_id), {})
        topic = q_obj.get("topic", "General")

        question_marks_detail.append({
            "q_num":      i + 1,
            "topic":      topic,
            "bloom":      q_obj.get("bloom_level", "remember"),
            "difficulty": round(q_obj.get("difficulty", 0.5), 2),
            "is_correct": is_correct,
            "attempts":   attempt,
            "hints_used": a.get("hints_used", 0),
            "marks":      pts,
            "max_marks":  100,
        })

    final_score = round(sum(weighted_scores) / len(weighted_scores), 1)
    total_marks_earned = sum(weighted_scores)
    total_marks_possible = len(weighted_scores) * 100


    # Difficulty progression
    diff_progression = []
    d = state.get("current_difficulty", 0.5)
    for a in answers:
        if a.get("is_correct"):
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
        "final_score":             final_score,
        "total_marks_earned":      total_marks_earned,
        "total_marks_possible":    total_marks_possible,
        "question_marks_detail":   question_marks_detail,
        "total_questions":         len(questions),
        "total_answered":          len(answers),
        "topic_scores":            state.get("topic_scores", {}),
        "bloom_scores":            state.get("bloom_scores", {}),
        "difficulty_progression":  diff_progression,
        "avg_attempts":            round(avg_attempts, 2),
        "avg_hints_used":          round(avg_hints, 2),
        "total_time_sec":          total_time_sec,
        "total_time_min":          round(total_time_sec / 60, 1),
        "weak_topics":             state.get("weak_topics", []),
        "strong_topics":           state.get("strong_topics", []),
        "recommendations":         state.get("recommendations", []),
        # Research metrics
        "avg_grounding_score":     round(avg_grounding, 3),
        "flagged_questions_count":  flagged_count,
        "flagged_questions_pct":    flagged_pct,
        "agent_logs":              logs
    }

    logs.append(f"[AnalyticsAgent] Final score={final_score}% | grounding={avg_grounding:.3f} | flagged={flagged_pct}%")
    logger.info(f"[AnalyticsAgent] Done | score={final_score}%")

    return {
        "final_score":      final_score,
        "analytics_report": report,
        "agent_logs":       logs
    }
