from pydantic import BaseModel
from typing import Dict, List, Optional

class AnalyticsResponse(BaseModel):
    session_id: str
    final_score: float
    total_questions: int
    total_answered: int
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
