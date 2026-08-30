"""
Analytics Router — Retrieve final session analytics + submit feedback.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.schemas.analytics import AnalyticsResponse, FeedbackRequest, FeedbackResponse
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
        correct_count=report.get("correct_count", 0),
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
        flagged_questions_pct=report.get("flagged_questions_pct", 0.0),
        recommendations_pending=report.get("recommendations_pending", False),
    )


@router.post("/{session_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(session_id: str, body: FeedbackRequest):
    """
    Submit post-quiz star rating + optional comment.
    Called automatically after the results page loads (WhatsApp-call style prompt).
    """
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.save_feedback(session_id, body.rating, body.comment)
    logger.info(f"Feedback received | session={session_id} rating={body.rating}")

    return FeedbackResponse(
        status="ok",
        message="Thank you for your feedback!"
    )
