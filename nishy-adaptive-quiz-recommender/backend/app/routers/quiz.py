"""
Quiz Router — Get questions and submit answers.
"""
import logging
from concurrent.futures import Future
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas.quiz import (
    AdvanceQuestionRequest,
    AdvanceQuestionResponse,
    QuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.services.db_service import DbService
from app.graph.graph import get_graph
from app.agents.analytics_agent import analytics_agent
from app.agents.adaptive_agent import adaptive_agent
from app.agents.quiz_agent import quiz_agent
from app.agents.recommendation_agent import recommendation_agent
from app.services.question_prefetch import prefetch_next_question
from app.services.session_work import submit_session_work

logger = logging.getLogger(__name__)
router = APIRouter()
db = DbService()
MCQ_OPTION_KEYS = {"1", "2", "3", "4", "5"}
_retry_jobs: dict[str, Future] = {}


def _retry_generation(session_id: str) -> None:
    """Repair a failed setup from its saved material without resetting answers."""
    from app.routers.session import _session_errors, _session_logs

    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    try:
        state = dict(graph.get_state(config).values)
        state.update(error=None, retry_count=0)
        graph.update_state(config, {"error": None, "retry_count": 0})
        generated = quiz_agent(state)
        graph.update_state(config, generated, as_node="quiz_generate")
        combined = {**state, **generated}
        index = int(combined.get("current_q_index", 0))
        ready = len(combined.get("questions", [])) > index and not generated.get("error")
        _session_logs[session_id] = combined.get("agent_logs", [])
        if ready:
            _session_errors.pop(session_id, None)
            db.update_session_progress(session_id, combined.get("topics", []), len(combined.get("raw_chunks", [])))
            db.update_session_status(session_id, "ready")
        else:
            _session_errors[session_id] = generated.get("error") or "Could not prepare this question. Please retry."
            db.update_session_status(session_id, "error")
    except Exception:
        logger.exception("Quiz retry failed | session=%s", session_id)
        _session_errors[session_id] = "Could not prepare this question. Please retry."
        db.update_session_status(session_id, "error")


@router.post("/{session_id}/retry-generation")
def retry_question_generation(session_id: str) -> dict:
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    snapshot = get_graph().get_state({"configurable": {"thread_id": session_id}})
    state = dict(snapshot.values if snapshot else {})
    if not state:
        raise HTTPException(status_code=409, detail="Study material is no longer available. Please start a new quiz.")
    if len(state.get("questions", [])) > int(state.get("current_q_index", 0)):
        db.update_session_status(session_id, "ready")
        return {"status": "ready"}
    previous_job = _retry_jobs.get(session_id)
    if previous_job is not None and not previous_job.done():
        return {"status": "processing"}
    db.update_session_status(session_id, "processing")
    _retry_jobs[session_id] = submit_session_work(session_id, _retry_generation, session_id)
    return {"status": "processing"}


def _continue_session_after_response(session_id: str, quiz_complete: bool) -> None:
    """Do expensive generation/recommendation work after answer response."""
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    try:
        snapshot = graph.get_state(config)
        state = dict(snapshot.values if snapshot else {})
        if quiz_complete:
            # Publish core marks immediately; enrich notes/resources afterwards.
            provisional = analytics_agent(state)
            provisional_report = dict(provisional.get("analytics_report", {}))
            provisional_report["recommendations_pending"] = True
            provisional["analytics_report"] = provisional_report
            graph.update_state(config, provisional)
            db.record_report(session_id, provisional_report)

            enriched_state = {**state, **provisional}
            # Publish source-extractive notes before slower model expansion
            # and live resource discovery finish.
            quick_recommendations = recommendation_agent(enriched_state, fast=True)
            quick_state = {**enriched_state, **quick_recommendations}
            quick_analytics = analytics_agent(quick_state)
            quick_report = dict(quick_analytics.get("analytics_report", {}))
            quick_report["recommendations_pending"] = True
            quick_analytics["analytics_report"] = quick_report
            graph.update_state(config, {**quick_recommendations, **quick_analytics})

            recommendations = recommendation_agent(enriched_state)
            enriched_state.update(recommendations)
            completed = analytics_agent(enriched_state)
            completed_report = dict(completed.get("analytics_report", {}))
            completed_report["recommendations_pending"] = False
            completed["analytics_report"] = completed_report
            graph.update_state(config, {**recommendations, **completed})
            db.record_report(session_id, completed_report)
        else:
            # Resume from the post-evaluation interrupt: adaptive -> generate.
            continued = graph.invoke(None, config=config)
            if continued.get("error") and len(continued.get("questions", [])) <= int(continued.get("current_q_index", 0)):
                from app.routers.session import _session_errors, _session_logs
                _session_errors[session_id] = str(continued["error"])
                _session_logs[session_id] = continued.get("agent_logs", [])
                db.update_session_status(session_id, "error")
                return
            # Replenish look-ahead so the following Next click is also instant.
            prefetch_next_question(session_id)
    except Exception:
        logger.exception("Background continuation failed | session=%s", session_id)


def _continue_direct_skip(session_id: str) -> None:
    """Adapt and refill after Next was used before any answer submission."""
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)
    state = dict(snapshot.values if snapshot else {})
    adaptive_update = adaptive_agent(state)
    graph.update_state(config, adaptive_update)
    adapted_state = {**state, **adaptive_update}
    generated = quiz_agent(adapted_state)
    graph.update_state(config, generated)


@router.get("/{session_id}/question", response_model=QuestionResponse)
def get_current_question(session_id: str):
    """
    Get the current question for a session.
    Returns the question at the current index from the graph state.
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

    if (not questions or q_idx >= len(questions)) and state.get("error"):
        raise HTTPException(
            status_code=503,
            detail=f"Question generation stopped after retries: {state['error']}",
        )

    if not questions or q_idx >= len(questions):
        raise HTTPException(
            status_code=404,
            detail="No question available. Session may still be processing."
        )

    question = questions[q_idx]

    # Validate MCQ options — but treat grounding issues as a soft warning (is_flagged)
    # rather than hard-failing so that the quiz can continue.
    if question.get("q_type") == "mcq":
        options = question.get("options") or {}
        if set(options) != MCQ_OPTION_KEYS:
            raise HTTPException(status_code=500, detail="Generated MCQ does not contain exactly five options")

    # Mark question as flagged if grounding did not pass, but do NOT block progress.
    is_flagged = question.get("grounding_status") not in {"grounded", "topic_model"}

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
        grounding_status=question["grounding_status"],
        source_file=question["source_file"],
        page_number=question["page_number"],
        is_flagged=is_flagged,
    )


@router.post("/{session_id}/answer", response_model=SubmitAnswerResponse)
def submit_answer(session_id: str, req: SubmitAnswerRequest, background_tasks: BackgroundTasks):
    """
    Submit a student's answer. Triggers evaluation + adaptive update.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        state_snapshot = graph.get_state(config)
        state = state_snapshot.values if state_snapshot else {}
        questions = state.get("questions", [])
        q_idx = state.get("current_q_index", 0)
        if q_idx >= len(questions):
            raise HTTPException(status_code=409, detail="No active question is available for this session")
        if req.q_id and req.q_id != questions[q_idx].get("q_id"):
            raise HTTPException(status_code=409, detail="This answer belongs to an outdated question")
        if q_idx < len(questions) and questions[q_idx].get("q_type") == "mcq":
            if req.answer not in MCQ_OPTION_KEYS:
                raise HTTPException(status_code=422, detail="MCQ answer must be a value from 1 through 5")

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer processing failed: {e}")

    # Get last answer result
    answers = final_state.get("answers", [])
    if not answers:
        raise HTTPException(status_code=500, detail="No answer record found")

    last_answer = answers[-1]
    db.record_attempt(session_id, last_answer)
    questions = final_state.get("questions", [])
    q_idx = final_state.get("current_q_index", 0)
    requested_questions = final_state.get("num_questions", 0)
    quiz_complete = requested_questions > 0 and q_idx >= requested_questions
    next_question_available = q_idx < len(questions)

    if not quiz_complete and not next_question_available and final_state.get("error"):
        logger.error(
            "Next-question generation exhausted | session=%s | q_index=%s | error=%s",
            session_id,
            q_idx,
            final_state.get("error"),
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "The next source-grounded question could not be generated after retries. "
                "Please start a new session or use a document with more distinct syllabus content."
            ),
        )

    answered_question = next(
        (question for question in questions if question.get("q_id") == last_answer.get("q_id")),
        {},
    )
    terminal_attempt = last_answer["is_correct"] or last_answer["attempts"] >= 4
    if terminal_attempt:
        # Start immediately rather than waiting for FastAPI's response-stage
        # background queue. Per-session locking also prevents prefetch races.
        submit_session_work(
            session_id, _continue_session_after_response, session_id, quiz_complete
        )

    # Adaptive pipeline stores the validated hint explicitly in attempt state.
    hint_text = last_answer.get("hint")
    if not last_answer["is_correct"] and last_answer["attempts"] < 4:
        if not hint_text:
            raw_fb = last_answer.get("feedback", "")
            if raw_fb.startswith("Incorrect. "):
                hint_text = raw_fb[len("Incorrect. "):]
            else:
                hint_text = raw_fb

    return SubmitAnswerResponse(
        is_correct=last_answer["is_correct"],
        score=last_answer["score"],
        feedback=last_answer["feedback"],
        hint=hint_text,
        hints_used=last_answer.get("hints_used", 0),
        attempts=last_answer["attempts"],
        next_question_available=next_question_available,
        quiz_complete=quiz_complete,
        correct_answer=last_answer.get("correct_answer"),
        correct_answer_text=last_answer.get("correct_answer_text"),
        explanation=last_answer.get("explanation"),
    )


@router.post("/{session_id}/advance", response_model=AdvanceQuestionResponse)
def advance_open_ended_question(session_id: str, req: AdvanceQuestionRequest):
    """Finalize or skip a structured/essay item, then continue adaptively."""
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)
    state = dict(snapshot.values if snapshot else {})
    questions = list(state.get("questions", []))
    q_idx = int(state.get("current_q_index", 0))
    if q_idx >= len(questions):
        raise HTTPException(status_code=409, detail="No active question is available")
    question = questions[q_idx]
    if req.q_id != question.get("q_id"):
        raise HTTPException(status_code=409, detail="This action belongs to an outdated question")
    if question.get("q_type") not in ("structured", "essay"):
        raise HTTPException(status_code=422, detail="Advance is only available for structured and essay questions")

    answers = list(state.get("answers", []))
    matching_indexes = [
        index for index, answer in enumerate(answers)
        if answer.get("q_id") == question.get("q_id")
    ]
    had_attempt = bool(matching_indexes)
    if matching_indexes:
        last_index = matching_indexes[-1]
        finalized = dict(answers[last_index])
        if finalized.get("is_terminal"):
            raise HTTPException(status_code=409, detail="This question has already been finalized")
    else:
        finalized = {
            "q_id": question["q_id"],
            "student_answer": "",
            "is_correct": False,
            "score": 0.0,
            "attempts": 1,
            "hints_used": 0,
            "time_taken_sec": 0,
            "feedback": "Question skipped.",
            "misconception": None,
            "hint": None,
            "hint_level": None,
        }
        answers.append(finalized)
        last_index = len(answers) - 1

    model_answer = question.get("model_answer") or "No model answer is available."
    finalized["is_terminal"] = True
    finalized["correct_answer"] = model_answer
    finalized["correct_answer_text"] = model_answer
    finalized["explanation"] = model_answer
    finalized["feedback"] = (
        f"{str(finalized.get('feedback', '')).strip()}\n\n"
        f"**Detailed Explanation:**\n{model_answer}"
    ).strip()
    answers[last_index] = finalized
    db.record_attempt(session_id, finalized)

    topic_scores = dict(state.get("topic_scores", {}))
    bloom_scores = dict(state.get("bloom_scores", {}))
    topic = question.get("topic", "General")
    bloom = question.get("bloom_level", "remember")
    topic_scores.setdefault(topic, {"correct": 0, "total": 0})
    bloom_scores.setdefault(bloom, {"correct": 0, "total": 0})
    topic_scores[topic]["total"] += 1
    bloom_scores[bloom]["total"] += 1
    if finalized.get("is_correct"):
        topic_scores[topic]["correct"] += 1
        bloom_scores[bloom]["correct"] += 1

    new_idx = q_idx + 1
    requested = int(state.get("num_questions", 0))
    quiz_complete = requested > 0 and new_idx >= requested
    graph.update_state(config, {
        "answers": answers,
        "topic_scores": topic_scores,
        "bloom_scores": bloom_scores,
        "current_q_index": new_idx,
        "_skip_requested": True,
        "_pending_answer": "",
    })
    if quiz_complete or had_attempt:
        submit_session_work(
            session_id, _continue_session_after_response, session_id, quiz_complete
        )
    else:
        submit_session_work(session_id, _continue_direct_skip, session_id)

    response_result = SubmitAnswerResponse(
        is_correct=bool(finalized.get("is_correct")),
        score=float(finalized.get("score", 0.0)),
        feedback=str(finalized.get("feedback", "")),
        hint=finalized.get("hint"),
        hints_used=int(finalized.get("hints_used", 0)),
        attempts=int(finalized.get("attempts", 1)),
        next_question_available=new_idx < len(questions),
        quiz_complete=quiz_complete,
        correct_answer=str(model_answer),
        correct_answer_text=str(model_answer),
        explanation=str(model_answer),
    )
    return AdvanceQuestionResponse(quiz_complete=quiz_complete, result=response_result)
