from pydantic import BaseModel
from typing import Optional, Literal, List


class CreateSessionRequest(BaseModel):
    document_ids: List[str] = []
    topic: Optional[str] = None
    subject: str = "Sri Lankan G.C.E. A/L Biology"
    student_id: str = "student_001"
    exam_type: Literal["mcq", "fill_blank", "structured", "essay"] = "mcq"
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
    is_topic_session: bool = False  # True when quiz was started with a Biology topic (no documents)
