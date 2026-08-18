"""
Evaluation Agent — Evaluates student answers.
Modes: MCQ (rule-based), Structured (LLM rubric), Essay (holistic LLM).
Includes progressive hint generation (3 levels).
"""
import uuid
import json
import logging
from dotenv import load_dotenv

from app.services.llm_service import LlmService
from app.services.rag_service import RagService
from app.graph.state import AssessmentState, AnswerRecord

load_dotenv()
logger = logging.getLogger(__name__)

STRUCTURED_EVAL_PROMPT = """
You are an examiner at SLIIT, Sri Lanka.

Question: {question}
Model Answer: {model_answer}
Marks Breakdown: {marks_breakdown}

Student's Answer:
{student_answer}

Evaluate strictly using the marks breakdown. Award partial marks.
Return ONLY valid JSON:
{{
    "score": 0.75,
    "marks_awarded": {{"content": 32, "accuracy": 24, "terminology": 15, "examples": 8}},
    "feedback": "Constructive feedback paragraph here.",
    "misconception": "State any misconception identified, or null.",
    "is_correct": false
}}

Note: award minimum 0.2 score if any correct point was made. Zero only for completely wrong.
"""

ESSAY_EVAL_PROMPT = """
You are an examiner at SLIIT, Sri Lanka.

Question: {question}
Model Answer / Key Points: {model_answer}

Student's Essay:
{student_answer}

Evaluate using this rubric. Return ONLY valid JSON:
{{
    "score": 0.70,
    "rubric_scores": {{"accuracy": 25, "completeness": 18, "structure": 15, "terminology": 12, "critical_thinking": 8}},
    "feedback": "Detailed holistic feedback here.",
    "misconception": "Any misconception or null.",
    "is_correct": false
}}

Max marks: accuracy/30, completeness/25, structure/20, terminology/15, critical_thinking/10
"""

HINT_PROMPTS = [
    """Context from the uploaded material:
{context}

Question: {question}

Give a LEVEL 1 hint — conceptual, general. Do NOT reveal the answer or mention the correct option.
Help the student think about the underlying concept of '{topic}'.""",

    """Context from the uploaded material:
{context}

Question: {question}

Give a LEVEL 2 hint — more focused. Reference a specific concept or term from the material.
Do NOT state the answer. Guide the student to the right approach for '{topic}'.""",

    """Context from the uploaded material:
{context}

Question: {question}

Give a LEVEL 3 hint — near-direct. Walk the student step-by-step toward the answer for '{topic}'.
Do NOT state the answer letter or the complete answer. Encourage reasoning."""
]


def _generate_hint(llm: LlmService, rag: RagService,
                   question: dict, hint_level: int,
                   collection_id: str) -> str:
    """Generate a RAG-grounded hint at the specified level (0-indexed)."""
    chunks = rag.retrieve(collection_id, question["topic"], k=2)
    context = "\n".join([c["text"] for c in chunks]) if chunks else "Use your knowledge of the topic."
    prompt = HINT_PROMPTS[min(hint_level, 2)].format(
        context=context,
        question=question["question"],
        topic=question["topic"]
    )
    try:
        return llm.call(prompt, temperature=0.3)
    except Exception as e:
        logger.error(f"Hint generation failed: {e}")
        return f"Think carefully about the concept of '{question['topic']}' from your study material."


def evaluation_agent(state: AssessmentState) -> dict:
    """
    Evaluation Agent.
    Input:  state['_pending_answer'], state['_answer_time_sec'], state['current_q_index']
    Output: state['answers'], state['topic_scores'], state['bloom_scores'], state['current_q_index']
    """
    logger.info(f"[EvaluationAgent] Starting | session={state['session_id']}")
    llm = LlmService()
    rag = RagService()
    logs = list(state.get("agent_logs", []))
    answers = list(state.get("answers", []))

    q_idx = state.get("current_q_index", 0)
    questions = state.get("questions", [])

    if q_idx >= len(questions):
        return {"agent_logs": logs}

    question = questions[q_idx]
    student_answer = state.get("_pending_answer", "").strip()
    time_taken = state.get("_answer_time_sec", 0)

    # Count previous attempts for this question
    prev_attempts = [a for a in answers if a.get("q_id") == question["q_id"]]
    attempt_num = len(prev_attempts) + 1
    prev_hints = sum(a.get("hints_used", 0) for a in prev_attempts)

    result: AnswerRecord = {
        "q_id":           question["q_id"],
        "student_answer": student_answer,
        "is_correct":     False,
        "score":          0.0,
        "attempts":       attempt_num,
        "hints_used":     0,
        "time_taken_sec": time_taken,
        "feedback":       "",
        "misconception":  None
    }

    q_type = question.get("q_type", "mcq")

    # ── MCQ: Rule-based evaluation ────────────────
    if q_type == "mcq":
        is_correct = student_answer.upper() == question["correct_answer"].upper()
        result["is_correct"] = is_correct
        result["score"] = 1.0 if is_correct else 0.0

        if is_correct:
            result["feedback"] = f"✅ Correct! {question.get('model_answer', '')}"
        elif attempt_num <= 3:
            # Give hint (counts as 1 hint used)
            hint = _generate_hint(llm, rag, question, attempt_num - 1,
                                   state["chroma_collection_id"])
            result["feedback"] = f"❌ Incorrect. {hint}"
            result["hints_used"] = prev_hints + 1
        else:
            result["feedback"] = f"❌ The correct answer is {question['correct_answer']}. {question.get('model_answer', '')}"

    # ── Structured: LLM rubric evaluation ─────────
    elif q_type == "structured":
        marks_breakdown = question.get(
            "marks_breakdown",
            {"content": 40, "accuracy": 30, "terminology": 20, "examples": 10}
        )
        prompt = STRUCTURED_EVAL_PROMPT.format(
            question=question["question"],
            model_answer=question["model_answer"],
            marks_breakdown=json.dumps(marks_breakdown),
            student_answer=student_answer
        )
        try:
            eval_data = llm.call_json(prompt, temperature=0.2)
            result["score"]        = float(eval_data.get("score", 0.0))
            result["is_correct"]   = eval_data.get("is_correct", result["score"] >= 0.5)
            result["feedback"]     = eval_data.get("feedback", "")
            result["misconception"] = eval_data.get("misconception")
        except Exception as e:
            result["feedback"] = f"Evaluation error: {e}. Please try again."
            logs.append(f"[EvaluationAgent] Structured eval failed: {e}")

    # ── Essay: Holistic LLM rubric ─────────────────
    elif q_type == "essay":
        prompt = ESSAY_EVAL_PROMPT.format(
            question=question["question"],
            model_answer=question["model_answer"],
            student_answer=student_answer
        )
        try:
            eval_data = llm.call_json(prompt, temperature=0.2)
            result["score"]        = float(eval_data.get("score", 0.0))
            result["is_correct"]   = result["score"] >= 0.5
            result["feedback"]     = eval_data.get("feedback", "")
            result["misconception"] = eval_data.get("misconception")
        except Exception as e:
            result["feedback"] = f"Evaluation error: {e}. Please try again."
            logs.append(f"[EvaluationAgent] Essay eval failed: {e}")

    answers.append(result)

    # Update topic scores
    topic_scores = dict(state.get("topic_scores", {}))
    bloom_scores  = dict(state.get("bloom_scores", {}))
    topic = question["topic"]
    bloom = question.get("bloom_level", "remember")

    topic_scores.setdefault(topic, {"correct": 0, "total": 0})
    bloom_scores.setdefault(bloom,  {"correct": 0, "total": 0})
    topic_scores[topic]["total"] += 1
    bloom_scores[bloom]["total"] += 1
    if result["is_correct"]:
        topic_scores[topic]["correct"] += 1
        bloom_scores[bloom]["correct"] += 1

    # Advance question index only if correct or max attempts reached
    new_idx = q_idx
    if result["is_correct"] or attempt_num >= 3:
        new_idx = q_idx + 1

    logs.append(f"[EvaluationAgent] Q{q_idx+1} | correct={result['is_correct']} | "
                f"score={result['score']:.2f} | attempt={attempt_num}")
    logger.info(f"[EvaluationAgent] Done | correct={result['is_correct']}")

    return {
        "answers":         answers,
        "topic_scores":    topic_scores,
        "bloom_scores":    bloom_scores,
        "current_q_index": new_idx,
        "_pending_answer": "",
        "agent_logs":      logs
    }
