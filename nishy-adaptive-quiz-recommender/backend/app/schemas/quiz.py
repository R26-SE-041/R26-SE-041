from pydantic import BaseModel
from typing import Optional, Dict

class QuestionResponse(BaseModel):
    q_id: str
    q_index: int
    total_questions: int
    question: str
    q_type: str
    options: Optional[Dict[str, str]] = None
    topic: str
    bloom_level: str
    difficulty: float
    grounding_score: float
    is_flagged: bool = False

class SubmitAnswerRequest(BaseModel):
    q_id: str
    answer: str
    time_taken_sec: int = 0

class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    score: float
    feedback: str
    hints_used: int
    attempts: int
    next_question_available: bool
    quiz_complete: bool = False
