"""
Analytics Router — Retrieve final session analytics.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.schemas.analytics import AnalyticsResponse
from app.services.db_service import DbService
from app.graph.graph import get_graph

logger = logging.getLogger(__name__)
router = APIRouter()
db = DbService()


@router.get("/{session_id}/report", response_model=AnalyticsResponse)
def get_analytics(session_id: str):
    """
    Get the complete analytics report for a completed session.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        state_snapshot = graph.get_state(config)
        state = state_snapshot.values if state_snapshot else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"State retrieval failed: {e}")

    report = state.get("analytics_report", {})
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Analytics not available. Complete the quiz first."
        )

    return AnalyticsResponse(
        session_id=session_id,
        final_score=report.get("final_score", 0.0),
        total_marks_earned=report.get("total_marks_earned"),
        total_marks_possible=report.get("total_marks_possible"),
        question_marks_detail=report.get("question_marks_detail"),
        total_questions=report.get("total_questions", 0),
        total_answered=report.get("total_answered", 0),
        topic_scores=report.get("topic_scores", {}),
        bloom_scores=report.get("bloom_scores", {}),
        difficulty_progression=report.get("difficulty_progression", []),
        avg_attempts=report.get("avg_attempts", 0.0),
        avg_hints_used=report.get("avg_hints_used", 0.0),
        total_time_min=report.get("total_time_min", 0.0),
        weak_topics=report.get("weak_topics", []),
        strong_topics=report.get("strong_topics", []),
        recommendations=report.get("recommendations", []),
        avg_grounding_score=report.get("avg_grounding_score", 0.0),
        flagged_questions_count=report.get("flagged_questions_count", 0),
        flagged_questions_pct=report.get("flagged_questions_pct", 0.0)
    )
