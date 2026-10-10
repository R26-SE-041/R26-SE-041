"""
Evaluation Agent — Evaluates student answers.
Modes: MCQ (rule-based), Structured (LLM rubric), Essay (holistic LLM).
Includes progressive hint generation (3 levels).
"""
import uuid
import json
import logging
import re
import unicodedata
from collections import Counter
from dotenv import load_dotenv

from app.services.llm_service import LlmService
from app.services.rag_service import RagService
from app.services.hint_pipeline import generate_adaptive_hint
from app.graph.state import AssessmentState, AnswerRecord
from app.agents.quiz_agent import _DEFAULT_MARKS_BREAKDOWN

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
    """Context from the student's uploaded material:
{context}

Question: {question}
Topic: {topic}

The student answered INCORRECTLY on attempt 1.

Generate a LEVEL 1 HINT (HARD). It must be challenging but coherent.

ABSOLUTE RULES — violating any of these is a failure:
- Formulate the hint as a conceptual explanation, NOT as a question. Do NOT ask any questions.
- Adopt a strict Sri Lankan university academic standard (e.g., SLIIT standard).
- Give only a subtle conceptual nudge: identify the underlying principle or relationship the student should reconsider.
- Make the student reason deeply, but do not produce vague, repetitive, contradictory, or nonsensical text.
- Do NOT explicitly state or give away the correct option (1/2/3/4/5) or explain why a specific answer is correct.
- Do NOT quote or closely repeat the wording of any answer option.
- Do NOT directly explain how the concept applies to the specific scenario in the question.
- Keep it to 2-3 sentences.

Return ONLY the hint text. No preamble.""",

    """Context from the student's uploaded material:
{context}

Question: {question}
Topic: {topic}

The student answered INCORRECTLY on attempts 1 and 2.

Generate a LEVEL 2 HINT (MEDIUM). It must focus the student's reasoning without solving the question.

ABSOLUTE RULES — violating any of these is a failure:
- Formulate the hint as a conceptual explanation, NOT as a question. Do NOT ask any questions.
- Adopt a strict Sri Lankan university academic standard.
- Explain the relevant mechanism or distinction at moderate depth, then indicate what relationship the student should use.
- Make the student think deeply, but keep every sentence clear, relevant, and non-repetitive.
- Do NOT explicitly state the correct option (1/2/3/4/5).
- Do NOT say "therefore the answer is...", "this means you should pick...".
- Do NOT quote, paraphrase too closely, endorse, reject, or eliminate any answer option.
- Keep it to 3-4 sentences.

Return ONLY the hint text. No preamble.""",

    """Context from the student's uploaded material:
{context}

Question: {question}
Topic: {topic}

The student answered INCORRECTLY on all 3 attempts.

Generate a LEVEL 3 HINT (EASY). It must refresh the relevant lesson without solving the question.

ABSOLUTE RULES — violating any of these is a failure:
- Formulate the hint as a conceptual explanation, NOT as a question. Do NOT ask any questions.
- Adopt a strict Sri Lankan university academic standard.
- Briefly recap the definition, purpose, and decision rule needed for this question, then tell the student how to apply that rule.
- Keep it clear and memorable, like a summary of the relevant lesson.
- UNDER NO CIRCUMSTANCES should you reveal the direct answer or the correct option number (1/2/3/4/5). Do NOT directly explain the answer.
- Do NOT quote, paraphrase too closely, endorse, reject, or eliminate any answer option.
- Keep it to 3-4 concise, non-repetitive sentences.

Return ONLY the hint text. No preamble."""
]


def _clean_hint(text: str) -> str:
    """Remove common LLM wrappers and normalize whitespace."""
    cleaned = re.sub(r"```(?:text)?", "", (text or ""), flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    cleaned = re.sub(
        r"^\s*(?:level\s*[123]\s*)?(?:hard|medium|easy)?\s*hint\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _is_repetitive_or_malformed(text: str) -> bool:
    """Reject runaway/repetitive model output before it reaches the user."""
    if len(text) < 30 or len(text) > 900:
        return True

    words = re.findall(r"[a-z0-9]+", text.casefold())
    if len(words) < 6:
        return True

    if len(words) >= 15:
        five_grams = Counter(tuple(words[i:i + 5]) for i in range(len(words) - 4))
        most_common = max(five_grams.values(), default=1)
        if most_common >= 3 and (most_common * 5) / len(words) >= 0.25:
            return True

    sentences = [
        re.sub(r"\W+", " ", sentence.casefold()).strip()
        for sentence in re.split(r"[.!?]+", text)
        if sentence.strip()
    ]
    return any(
        count >= 2
        for sentence, count in Counter(sentences).items()
        if len(sentence.split()) >= 5
    )


def _reveals_mcq_answer(text: str, question: dict) -> bool:
    """Detect explicit option-number or exact correct-option disclosure."""
    answer_key = str(question.get("correct_answer", "")).strip().upper()
    if answer_key:
        key = re.escape(answer_key)
        disclosure_patterns = (
            rf"\b(?:answer|option|choice)\s*(?:is|:|=)?\s*{key}\b",
            rf"\b(?:choose|select|pick)\s+(?:option\s+)?{key}\b",
            rf"\(\s*{key}\s*\)",
            rf"\*\*\s*{key}\s*\*\*",
        )
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in disclosure_patterns):
            return True

    options = question.get("options") or {}
    correct_option = str(options.get(answer_key, "")).strip()
    normalized_hint = re.sub(r"\W+", " ", text.casefold()).strip()
    normalized_option = re.sub(r"\W+", " ", correct_option.casefold()).strip()
    option_words = normalized_option.split()
    if len(option_words) >= 2 and normalized_option in normalized_hint:
        return True
    if len(option_words) == 1 and len(normalized_option) >= 5:
        return bool(re.search(rf"\b{re.escape(normalized_option)}\b", normalized_hint))
    return False


def _fallback_hint(question: dict, hint_level: int) -> str:
    """Safe fallback used only when the model repeatedly returns unusable text."""
    topic = str(question.get("topic") or "this topic").strip()
    fallbacks = (
        f"Revisit the core principle behind {topic} and separate its purpose from its implementation details. Focus on which relationship the scenario is testing before comparing the choices.",
        f"Recall how {topic} distinguishes responsibilities, mechanisms, and outcomes. Apply that distinction to each part of the scenario and compare how the choices represent those roles.",
        f"Summarize {topic} using three points: what it is, what purpose it serves, and the rule that determines when it applies. Match that rule to the scenario while checking that every part of a choice is accurate.",
    )
    fallback = fallbacks[min(max(hint_level, 0), 2)]
    if _reveals_mcq_answer(fallback, question):
        return (
            "Recall the relevant concept's definition, purpose, and decision rule. "
            "Apply that rule to every part of the scenario, then compare the choices without relying on surface wording."
        )
    return fallback


def _generate_hint(llm: LlmService, rag: RagService,
                   question: dict, hint_level: int,
                   collection_id: str) -> str:
    """Generate a RAG-grounded hint at the specified level (0-indexed, 0=hard, 2=easy)."""
    try:
        chunks = rag.retrieve(collection_id, question["topic"], k=3)
    except Exception as e:
        logger.error(f"Hint context retrieval failed: {e}")
        chunks = []
    context = "\n\n".join([c["text"] for c in chunks]) if chunks else (
        "No source context is available. Do not use general knowledge or add facts."
    )
    prompt = HINT_PROMPTS[min(hint_level, 2)].format(
        context=context,
        question=question["question"],
        topic=question["topic"]
    )
    for generation_attempt in range(3):
        try:
            retry_instruction = ""
            if generation_attempt:
                retry_instruction = (
                    "\n\nYour previous output was rejected because it leaked the answer, repeated text, "
                    "or was malformed. Write a completely new, concise hint and obey every rule."
                )
            hint = _clean_hint(
                llm.call(prompt + retry_instruction)
            )
            if not _is_repetitive_or_malformed(hint) and not _reveals_mcq_answer(hint, question):
                return hint
            logger.warning(
                "Rejected unsafe hint output | level=%s | attempt=%s",
                hint_level + 1,
                generation_attempt + 1,
            )
        except Exception as e:
            logger.error(f"Hint generation failed on attempt {generation_attempt + 1}: {e}")

    return _fallback_hint(question, hint_level)


# Backward-compatible import name; the active implementation is the complete
# validated pipeline in app.services.hint_pipeline.
_generate_hint = generate_adaptive_hint


def _normalize_exact_answer(value: str) -> str:
    """Ignore casing and harmless whitespace/punctuation, but not synonyms."""
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    return re.sub(r"\s+", " ", normalized).strip(" .,:;!?\t\r\n")


def _local_open_ended_evaluation(student_answer: str, model_answer: str, q_type: str) -> dict:
    """Fast source-bound partial grading when the remote rubric model is cold."""
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "with",
    }
    student_terms = {
        token for token in re.findall(r"[a-z][a-z0-9-]{2,}", student_answer.casefold())
        if token not in stop_words
    }
    model_terms = {
        token for token in re.findall(r"[a-z][a-z0-9-]{2,}", model_answer.casefold())
        if token not in stop_words
    }
    coverage = len(student_terms & model_terms) / max(len(model_terms), 1)
    expected_words = 70 if q_type == "structured" else 140
    depth = min(len(student_answer.split()) / expected_words, 1.0)
    score = round(min(1.0, (coverage * 0.75) + (depth * 0.25)), 2)
    if not student_answer.strip():
        score = 0.0
    return {
        "score": score,
        "is_correct": score >= 0.5,
        "feedback": (
            f"Source-keyword coverage: {round(coverage * 100)}%; response depth: "
            f"{round(depth * 100)}%. Strengthen the missing biological relationships and justify each link."
        ),
        "misconception": None,
    }


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
    previous_hints = []
    for previous in prev_attempts:
        hint = str(previous.get("hint") or "").strip()
        if not hint and not previous.get("is_correct") and previous.get("attempts", 0) <= 3:
            feedback = str(previous.get("feedback") or "")
            hint = re.sub(r"^.*?Incorrect\.\s*", "", feedback, count=1).strip()
        if hint:
            previous_hints.append(hint)
    # hints_used is cumulative for this question, not a value to sum across
    # attempt records. A correct retry must retain the hints already consumed.
    prev_hints = min(
        sum(1 for a in prev_attempts if not a.get("is_correct") and a.get("attempts", 0) <= 3),
        3,
    )

    result: AnswerRecord = {
        "q_id":           question["q_id"],
        "student_answer": student_answer,
        "is_correct":     False,
        "score":          0.0,
        "attempts":       attempt_num,
        "hints_used":     prev_hints,
        "time_taken_sec": time_taken,
        "feedback":       "",
        "misconception":  None,
        "hint":           None,
        "hint_level":     None,
    }

    q_type = question.get("q_type", "mcq")

    # ── MCQ: Rule-based evaluation ────────────────
    if q_type == "mcq":
        is_correct = student_answer.upper() == question["correct_answer"].upper()
        result["is_correct"] = is_correct
        result["score"] = 1.0 if is_correct else 0.0

        correct_key = str(question["correct_answer"]).strip()
        correct_text = str((question.get("options") or {}).get(correct_key, "")).strip()
        # Option keys are internal and are reshuffled for display in the UI.
        # Never embed the internal number in human-readable feedback.
        correct_label = correct_text or "the source-supported option"
        explanation = question.get("model_answer") or (
            "Insufficient source context to provide a valid explanation."
        )

        if is_correct:
            result["feedback"] = (
                f"Correct. The correct answer is **{correct_label}**.\n\n"
                f"**Detailed Explanation:**\n{explanation}"
            )
            result["correct_answer"] = correct_key
            result["correct_answer_text"] = correct_text or None
            result["explanation"] = explanation
        elif attempt_num <= 3:
            # Attempts 1/2/3 → validated HARD/MEDIUM/EASY adaptive pipeline.
            hint_level = attempt_num - 1
            hint = generate_adaptive_hint(
                llm,
                rag,
                question,
                hint_level,
                state["chroma_collection_id"],
                previous_hints=previous_hints,
            )
            result["feedback"] = f"Incorrect. {hint}"
            result["hint"] = hint
            result["hint_level"] = ("HARD", "MEDIUM", "EASY")[hint_level]
            result["hints_used"] = attempt_num
        else:
            # All 4 attempts used → reveal correct answer with full explanation
            result["feedback"] = (
                f"The correct answer is **{correct_label}**.\n\n"
                f"**Detailed Explanation:**\n"
                f"{explanation}"
            )
            result["correct_answer"] = correct_key
            result["correct_answer_text"] = correct_text or None
            result["explanation"] = explanation

    # ── Structured: LLM rubric evaluation ─────────
    elif q_type == "fill_blank":
        correct_text = str(question.get("correct_answer", "")).strip()
        is_correct = _normalize_exact_answer(student_answer) == _normalize_exact_answer(correct_text)
        result["is_correct"] = is_correct
        result["score"] = 1.0 if is_correct else 0.0
        explanation = question.get("model_answer") or "Review the exact source-supported term and its biological role."

        if is_correct:
            result["feedback"] = f"Correct. **{correct_text}** completes the blank.\n\n**Detailed Explanation:**\n{explanation}"
            result["correct_answer"] = correct_text
            result["correct_answer_text"] = correct_text
            result["explanation"] = explanation
        elif attempt_num <= 3:
            hint_question = dict(question)
            hint_question["options"] = {"answer": correct_text}
            hint_question["correct_answer"] = "answer"
            hint = generate_adaptive_hint(
                llm, rag, hint_question, attempt_num - 1,
                state["chroma_collection_id"], previous_hints=previous_hints,
            )
            result["feedback"] = f"Incorrect. {hint}"
            result["hint"] = hint
            result["hint_level"] = ("HARD", "MEDIUM", "EASY")[attempt_num - 1]
            result["hints_used"] = attempt_num
        else:
            result["feedback"] = f"The exact answer is **{correct_text}**.\n\n**Detailed Explanation:**\n{explanation}"
            result["correct_answer"] = correct_text
            result["correct_answer_text"] = correct_text
            result["explanation"] = explanation

    elif q_type in ("structured", "essay"):
        # Open-ended work keeps the adaptive hint progression, while the API's
        # explicit advance action lets the learner move on at any point.
        if q_type == "structured":
            marks_breakdown = question.get("marks_breakdown") or _DEFAULT_MARKS_BREAKDOWN
            prompt = STRUCTURED_EVAL_PROMPT.format(
                question=question["question"],
                model_answer=question["model_answer"],
                marks_breakdown=json.dumps(marks_breakdown),
                student_answer=student_answer,
            )
        else:
            prompt = ESSAY_EVAL_PROMPT.format(
                question=question["question"],
                model_answer=question["model_answer"],
                student_answer=student_answer,
            )
        try:
            endpoint_warm = not hasattr(llm, "check_health") or llm.check_health()
            eval_data = (
                llm.call_json(prompt)
                if endpoint_warm
                else _local_open_ended_evaluation(
                    student_answer, question.get("model_answer", ""), q_type
                )
            )
            score = float(eval_data.get("score", 0.0))
            is_correct = bool(eval_data.get("is_correct", score >= 0.5)) if q_type == "structured" else score >= 0.5
            rubric_feedback = str(eval_data.get("feedback", "")).strip()
            misconception = eval_data.get("misconception")
        except Exception as e:
            score = 0.0
            is_correct = False
            rubric_feedback = ""
            misconception = None
            logs.append(f"[EvaluationAgent] {q_type.capitalize()} eval failed: {e}")

        result["score"] = score
        result["is_correct"] = is_correct
        result["misconception"] = misconception
        model_answer = question.get("model_answer") or "Insufficient source context to provide a valid explanation."

        if is_correct:
            result["feedback"] = (
                (f"{rubric_feedback}\n\n" if rubric_feedback else "")
                + f"**Detailed Explanation:**\n{model_answer}"
            )
            result["correct_answer"] = model_answer
            result["correct_answer_text"] = model_answer
            result["explanation"] = model_answer
            result["is_terminal"] = True
        elif attempt_num <= 3:
            hint = generate_adaptive_hint(
                llm,
                rag,
                question,
                attempt_num - 1,
                state["chroma_collection_id"],
                previous_hints=previous_hints,
            )
            result["feedback"] = (f"{rubric_feedback}\n\n" if rubric_feedback else "") + hint
            result["hint"] = hint
            result["hint_level"] = ("HARD", "MEDIUM", "EASY")[attempt_num - 1]
            result["hints_used"] = attempt_num
        else:
            result["feedback"] = (
                (f"{rubric_feedback}\n\n" if rubric_feedback else "")
                + f"**Detailed Explanation:**\n{model_answer}"
            )
            result["correct_answer"] = model_answer
            result["correct_answer_text"] = model_answer
            result["explanation"] = model_answer
            result["is_terminal"] = True

    answers.append(result)

    # Update topic scores
    topic_scores = dict(state.get("topic_scores", {}))
    bloom_scores  = dict(state.get("bloom_scores", {}))
    topic = question["topic"]
    bloom = question.get("bloom_level", "remember")

    terminal_attempt = result["is_correct"] or attempt_num >= 4
    if terminal_attempt:
        topic_scores.setdefault(topic, {"correct": 0, "total": 0})
        bloom_scores.setdefault(bloom,  {"correct": 0, "total": 0})
        topic_scores[topic]["total"] += 1
        bloom_scores[bloom]["total"] += 1
        if result["is_correct"]:
            topic_scores[topic]["correct"] += 1
            bloom_scores[bloom]["correct"] += 1

    # Advance question index only if correct or all hint attempts exhausted (attempt 4+)
    # Attempts 1/2/3 give L1/L2/L3 hints; attempt 4+ reveals the answer and moves on
    new_idx = q_idx
    if result["is_correct"] or attempt_num >= 4:
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
