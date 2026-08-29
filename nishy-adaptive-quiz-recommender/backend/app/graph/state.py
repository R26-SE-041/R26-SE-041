"""
LangGraph State Schema for Adaptive AI Assessment Platform.
This single TypedDict is the shared state across all agents.
"""
from typing import TypedDict, List, Optional, Literal, NotRequired


class QuestionRecord(TypedDict):
    """A single generated question."""
    q_id: str
    topic: str
    bloom_level: str          # remember|understand|apply|analyze|evaluate|create
    difficulty: float         # 0.0 to 1.0
    q_type: str               # mcq|fill_blank|structured|essay
    question: str
    options: Optional[dict]   # {"1", "2", "3", "4", "5"} — MCQ only
    correct_answer: str
    model_answer: str
    grounding_score: float    # Cosine similarity vs source (research metric)
    grounding_status: str     # grounded; rejected candidates never enter state
    source_file: str
    page_number: int
    retrieved_text: str
    source_chunk_ids: List[str]
    source_chunks: List[dict]


class AnswerRecord(TypedDict):
    """A student's answer to one question."""
    q_id: str
    student_answer: str
    is_correct: bool
    score: float              # 0.0-1.0 (partial marks supported)
    attempts: int
    hints_used: int
    time_taken_sec: int
    feedback: str
    misconception: Optional[str]
    hint: NotRequired[Optional[str]]
    hint_level: NotRequired[Optional[str]]  # HARD | MEDIUM | EASY
    correct_answer: NotRequired[Optional[str]]
    correct_answer_text: NotRequired[Optional[str]]
    explanation: NotRequired[Optional[str]]


class AssessmentState(TypedDict):
    """Complete shared state for the LangGraph assessment workflow."""

    # ── Session identifiers ────────────────────────────────
    session_id: str
    student_id: str
    subject: str

    # ── Ingestion ─────────────────────────────────────────
    document_ids: List[str]
    requested_topic: Optional[str]
    raw_chunks: List[dict]           # {chunk_id, text, source, page, heading}
    chroma_collection_id: str
    ingestion_status: str            # pending|done|error

    # ── Knowledge extraction ───────────────────────────────
    topics: List[str]
    topic_hierarchy: dict            # {topic: [subtopics]}
    concept_graph_json: str          # NetworkX serialized as JSON string
    bloom_tag_map: dict              # {topic: bloom_level}
    knowledge_status: str

    # ── Student preferences ────────────────────────────────
    exam_type: str                   # mcq|structured|essay
    num_questions: int
    difficulty_mode: str             # easy|medium|hard|adaptive
    time_limit_min: Optional[int]

    # ── Quiz planning & generation ─────────────────────────
    quiz_blueprint: List[dict]       # complete hidden concept plan for the quiz batch
    questions: List[QuestionRecord]
    current_q_index: int
    flagged_questions: List[str]     # q_ids with low grounding score

    # ── Student performance ────────────────────────────────
    answers: List[AnswerRecord]
    current_difficulty: float        # Adaptive difficulty level 0.0-1.0
    topic_scores: dict               # {topic: {correct, total}}
    bloom_scores: dict               # {bloom_level: {correct, total}}

    # ── Pending answer (set by API before evaluation) ──────
    _pending_answer: str
    _answer_time_sec: int

    # ── Output ────────────────────────────────────────────
    weak_topics: List[str]
    strong_topics: List[str]
    recommendations: List[dict]
    analytics_report: dict
    final_score: float

    # ── Control flow ───────────────────────────────────────
    error: Optional[str]
    retry_count: int
    agent_logs: List[str]            # Research logging
