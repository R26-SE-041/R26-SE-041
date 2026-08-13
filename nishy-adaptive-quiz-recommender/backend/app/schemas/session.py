from pydantic import BaseModel
from typing import Optional, Literal, List


class CreateSessionRequest(BaseModel):
    document_ids: List[str]
    student_id: str = "student_001"
    exam_type: Literal["mcq", "structured", "essay"] = "mcq"
    num_questions: Literal[5, 10, 20, 50] = 10
    difficulty_mode: Literal["easy", "medium", "hard", "adaptive"] = "adaptive"
    time_limit_min: Optional[int] = None


class StartSessionResponse(BaseModel):
    session_id: str
    status: str
    message: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str                  # processing | ready | error
    topics_detected: List[str] = []
    num_questions: int = 0
    message: str = ""
    chunk_count: int = 0
