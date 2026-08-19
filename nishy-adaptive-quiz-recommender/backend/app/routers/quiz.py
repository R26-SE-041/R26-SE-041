"""
Quiz Router — Get questions and submit answers.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.schemas.quiz import QuestionResponse, SubmitAnswerRequest, SubmitAnswerResponse
from app.services.db_service import DbService
from app.graph.graph import get_graph

logger = logging.getLogger(__name__)
router = APIRouter()
db = DbService()


@router.get("/{session_id}/question", response_model=QuestionResponse)
def get_current_question(session_id: str):
    """
    Get the current question for a session.
    Triggers quiz_agent to generate if not yet generated.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        state_snapshot = graph.get_state(config)
        state = state_snapshot.values if state_snapshot else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"State retrieval failed: {e}")

    questions = state.get("questions", [])
    q_idx = state.get("current_q_index", 0)
    num_questions = state.get("num_questions", 0)

    if not questions or q_idx >= len(questions):
        raise HTTPException(
            status_code=404,
            detail="No question available. Session may still be processing."
        )

    question = questions[q_idx]
    threshold = 0.55

    return QuestionResponse(
        q_id=question["q_id"],
        q_index=q_idx,
        total_questions=num_questions,
        question=question["question"],
        q_type=question["q_type"],
        options=question.get("options"),
        topic=question["topic"],
        bloom_level=question["bloom_level"],
        difficulty=question["difficulty"],
        grounding_score=question["grounding_score"],
        is_flagged=question["grounding_score"] < threshold
    )


@router.post("/{session_id}/answer", response_model=SubmitAnswerResponse)
def submit_answer(session_id: str, req: SubmitAnswerRequest):
    """
    Submit a student's answer. Triggers evaluation + adaptive update.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        # Inject student answer into state
        graph.update_state(
            config,
            {
                "_pending_answer":  req.answer,
                "_answer_time_sec": req.time_taken_sec
            }
        )
        # Resume graph execution (evaluation + adaptive)
        final_state = graph.invoke(None, config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer processing failed: {e}")

    # Get last answer result
    answers = final_state.get("answers", [])
    if not answers:
        raise HTTPException(status_code=500, detail="No answer record found")

    last_answer = answers[-1]
    questions = final_state.get("questions", [])
    q_idx = final_state.get("current_q_index", 0)
    quiz_complete = q_idx >= final_state.get("num_questions", 0)

    # Extract hint text from feedback if incorrect (hint is embedded after "❌ Incorrect. ")
    hint_text = None
    if not last_answer["is_correct"] and last_answer["attempts"] < 4:
        raw_fb = last_answer.get("feedback", "")
        # Strip the leading emoji prefix if present
        if raw_fb.startswith("❌ Incorrect. "):
            hint_text = raw_fb[len("❌ Incorrect. "):]
        else:
            hint_text = raw_fb

    return SubmitAnswerResponse(
        is_correct=last_answer["is_correct"],
        score=last_answer["score"],
        feedback=last_answer["feedback"],
        hint=hint_text,
        hints_used=last_answer.get("hints_used", 0),
        attempts=last_answer["attempts"],
        next_question_available=not quiz_complete,
        quiz_complete=quiz_complete
    )
