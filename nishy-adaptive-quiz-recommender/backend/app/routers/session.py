"""
Session Router — Create and manage assessment sessions.
POST /start — upload files + config in one multipart call (frontend-friendly)
GET  /{session_id}/status — poll for processing status
GET  /{session_id}/debug  — see agent logs for debugging
"""
import os
import uuid
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Body
from app.schemas.session import StartSessionResponse, SessionStatusResponse, CreateSessionRequest
from app.services.db_service import DbService
from app.graph.graph import get_graph
from app.graph.state import AssessmentState

logger = logging.getLogger(__name__)
router = APIRouter()
db = DbService()

# In-memory store for agent logs (for debugging)
_session_logs: dict = {}

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".jpg", ".jpeg", ".png"}


def _initial_state(
    session_id: str,
    student_id: str,
    exam_type: str,
    num_questions: int,
    difficulty_mode: str,
    time_limit_min: Optional[int],
    document_ids: list,
) -> AssessmentState:
    """Build the initial LangGraph state for a new session."""
    diff_map = {"easy": 0.2, "medium": 0.5, "hard": 0.8, "adaptive": 0.8}
    return {
        "session_id":             session_id,
        "student_id":             student_id,
        "document_ids":           document_ids,
        "raw_chunks":             [],
        "chroma_collection_id":   session_id,
        "ingestion_status":       "pending",
        "topics":                 [],
        "topic_hierarchy":        {},
        "concept_graph_json":     "{}",
        "bloom_tag_map":          {},
        "knowledge_status":       "pending",
        "exam_type":              exam_type,
        "num_questions":          num_questions,
        "difficulty_mode":        difficulty_mode,
        "time_limit_min":         time_limit_min,
        "quiz_blueprint":         [],
        "questions":              [],
        "current_q_index":        0,
        "flagged_questions":      [],
        "answers":                [],
        "current_difficulty":     diff_map.get(difficulty_mode, 0.5),
        "topic_scores":           {},
        "bloom_scores":           {},
        "_pending_answer":        "",
        "_answer_time_sec":       0,
        "weak_topics":            [],
        "strong_topics":          [],
        "recommendations":        [],
        "analytics_report":       {},
        "final_score":            0.0,
        "error":                  None,
        "retry_count":            0,
        "agent_logs":             [],
    }


def _run_setup_phase(session_id: str, state: AssessmentState):
    """
    Background task: ingestion → knowledge extraction → first question generation.
    """
    from app.services.llm_service import LlmService
    _session_logs[session_id] = ["[Setup] Starting..."]
    try:
        # Pre-flight: check Modal endpoint is reachable before running graph
        llm = LlmService()
        health = llm.check_health()
        _session_logs[session_id].append(f"[Setup] Modal health check: {health}")
        if not health:
            msg = "Modal endpoint unreachable. Run: modal deploy modal_inference/qwen_endpoint.py"
            _session_logs[session_id].append(f"[Setup] FATAL: {msg}")
            logger.error(f"Session {session_id}: {msg}")
            db.update_session_status(session_id, "error")
            return

        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}
        _session_logs[session_id].append("[Setup] Invoking graph...")
        final_state = graph.invoke(state, config=config)

        # Save agent logs from graph
        agent_logs = (final_state or {}).get("agent_logs", [])
        _session_logs[session_id].extend(agent_logs)

        # Only mark ready if questions were actually generated
        questions = final_state.get("questions", []) if final_state else []
        if questions:
            topics = final_state.get("topics", [])
            chunk_count = len(final_state.get("raw_chunks", []))
            db.update_session_progress(session_id, topics, chunk_count)
            db.update_session_status(session_id, "ready")
            _session_logs[session_id].append(f"[Setup] SUCCESS: {len(questions)} questions generated")
            logger.info(f"Session {session_id} setup complete | {len(questions)} question(s)")
        else:
            err = (final_state or {}).get("error") or "No questions generated"
            _session_logs[session_id].append(f"[Setup] FAILED: {err}")
            logger.error(f"Session {session_id} failed: {err}")
            for log in agent_logs[-10:]:
                logger.error(f"  {log}")
            db.update_session_status(session_id, "error")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _session_logs[session_id].append(f"[Setup] EXCEPTION: {type(e).__name__}: {e}")
        _session_logs[session_id].append(tb)
        logger.error(f"Session setup failed: {e}", exc_info=True)
        db.update_session_status(session_id, "error")



@router.post("/start", response_model=StartSessionResponse)
async def start_session(
    request: CreateSessionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Unified endpoint: create session using existing document_ids.
    Returns session_id immediately. Poll /status to know when ready.
    """
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="Must provide at least one document_id.")

    session_id = str(uuid.uuid4())

    # Persist to DB
    db.create_session({
        "session_id":           session_id,
        "student_id":           request.student_id,
        "exam_type":            request.exam_type,
        "num_questions":        request.num_questions,
        "difficulty_mode":      request.difficulty_mode,
        "time_limit_min":       request.time_limit_min,
        "status":               "processing",
        "chroma_collection_id": session_id,
    })

    # Pass document_ids into state instead of file paths
    state = _initial_state(
        session_id, request.student_id, request.exam_type,
        request.num_questions, request.difficulty_mode, request.time_limit_min, request.document_ids
    )

    background_tasks.add_task(_run_setup_phase, session_id, state)

    return StartSessionResponse(
        session_id=session_id,
        status="processing",
        message=f"{len(request.document_ids)} document(s) selected. Initializing session...",
    )


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
def get_session_status(session_id: str):
    """Poll this endpoint to check when the session is ready for quiz."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Read topics + chunk_count from DB (persisted after graph completes)
    import json
    topics_raw = session.get("topics_detected", "[]")
    try:
        topics = json.loads(topics_raw) if topics_raw else []
    except Exception:
        topics = []
    chunk_count = session.get("chunk_count", 0) or 0

    status = session["status"]
    msg_map = {
        "processing": "Processing your documents... (this may take up to 60s for topic extraction)",
        "ready":      "Ready! Start your quiz.",
        "error":      "Setup failed. Check that the Modal endpoint is deployed: modal deploy modal_inference/qwen_endpoint.py",
    }

    return SessionStatusResponse(
        session_id=session_id,
        status=status,
        topics_detected=topics,
        num_questions=session["num_questions"],
        message=msg_map.get(status, status),
        chunk_count=chunk_count,
    )


@router.get("/{session_id}/debug")
def debug_session(session_id: str):
    """Returns agent logs for debugging. Check this when status is 'error'."""
    logs = _session_logs.get(session_id, ["No logs captured for this session (may have run before server restart)"])
    session = db.get_session(session_id)
    status = session["status"] if session else "unknown"
    return {
        "session_id": session_id,
        "status": status,
        "log_count": len(logs),
        "logs": logs,
    }
