from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class AnalyticsResponse(BaseModel):
    session_id: str
    final_score: float
    total_marks_earned: Optional[int] = None
    total_marks_possible: Optional[int] = None
    question_marks_detail: Optional[List[Dict]] = None
    total_questions: int
    total_answered: int
    correct_count: int = 0
    topic_scores: Dict
    bloom_scores: Dict
    difficulty_progression: List[float]
    avg_attempts: float
    avg_hints_used: float
    total_time_min: float
    weak_topics: List[str]
    strong_topics: List[str]
    recommendations: List[Dict]
    avg_grounding_score: float
    flagged_questions_count: int
    flagged_questions_pct: float
    recommendations_pending: bool = False


class FeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Star rating 1–5")
    comment: Optional[str] = Field(None, max_length=500, description="Optional short comment")


class FeedbackResponse(BaseModel):
    status: str
    message: str
