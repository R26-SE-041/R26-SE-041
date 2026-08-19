"""
Quiz Agent — Plans quiz blueprint, generates grounded questions,
and verifies each question's grounding score.
"""
import os
import uuid
import json
import random
import logging
from typing import List, Tuple
from dotenv import load_dotenv

from app.services.llm_service import LlmService
from app.services.rag_service import RagService
from app.services.grounding_service import GroundingService
from app.graph.state import AssessmentState, QuestionRecord

load_dotenv()
logger = logging.getLogger(__name__)

# Difficulty bands → (label, bloom_level)
DIFF_BANDS = [
    (0.0,  0.33, "easy",   "remember"),
    (0.33, 0.66, "medium", "apply"),
    (0.66, 1.0,  "hard",   "analyze"),
]

INIT_DIFFICULTY = {"easy": 0.2, "medium": 0.5, "hard": 0.8, "adaptive": 0.8}

MCQ_PROMPT = """
Use ONLY the following context from the student's uploaded material.
Do NOT use external knowledge.

Context:
{context}

Generate a {bloom_level}-level Multiple Choice Question about "{topic}".
Difficulty: {diff_label} ({difficulty:.2f}/1.0)
Target university: SLIIT, Sri Lanka — emphasize application and reasoning at a Sri Lankan academic standard. Use local contexts and avoid foreign examples.

Return ONLY valid JSON:
{{
    "question": "The question text here?",
    "options": {{"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}},
    "correct_answer": "B",
    "model_answer": "Detailed explanation of the core concept and why B is the only correct answer. Do not just state it is correct, explain the reasoning behind it.",
    "explanation": "Brief explanation for feedback."
}}

Rules:
- All 4 options must be plausible (no obviously wrong distractors)
- Question must test a specific concept from the context
- Do not repeat any question already in the quiz
- Phrase the question directly as a real-world concept. Do NOT refer to "the context", "the document", "the text", "the uploaded material", or "the page".
- CRITICAL DIFFICULTY RULES:
  * HARD: The question MUST be extremely confusing and force the student to rack their brains (user mandaya pottu kulapura mathiri). It should be an indirect, complex scenario at a high Sri Lankan degree standard where the answer requires deep thinking to discover.
  * MEDIUM: The question should be about 15% less hard than the HARD level, but it MUST still be confusing and make the student think deeply to find the answer.
  * EASY: The question MUST be a direct, straightforward question (direct quizes kekanum).
"""

STRUCTURED_PROMPT = """
Use ONLY the following context from the student's uploaded material.
Do NOT use external knowledge.

Context:
{context}

Generate a {bloom_level}-level structured question about "{topic}".
Difficulty: {diff_label}
Target university: SLIIT, Sri Lanka — maintain a Sri Lankan academic standard and use local context/examples where applicable.

Return ONLY valid JSON:
{{
    "question": "The question text here?",
    "model_answer": "Detailed model answer covering all key points.",
    "correct_answer": "Summary of key points the student must include.",
    "marks_breakdown": {{"content": 40, "accuracy": 30, "terminology": 20, "examples": 10}}
}}

Rules:
- Phrase the question directly as a real-world concept. Do NOT refer to "the context", "the document", "the text", "the uploaded material", or "the page".
- CRITICAL DIFFICULTY RULES:
  * HARD: The question MUST be extremely confusing and force the student to rack their brains (user mandaya pottu kulapura mathiri). It should be an indirect, complex scenario at a high Sri Lankan degree standard where the answer requires deep thinking to discover.
  * MEDIUM: The question should be about 15% less hard than the HARD level, but it MUST still be confusing and make the student think deeply to find the answer.
  * EASY: The question MUST be a direct, straightforward question (direct quizes kekanum).
"""

ESSAY_PROMPT = """
Use ONLY the following context from the student's uploaded material.
Do NOT use external knowledge.

Context:
{context}

Generate an essay question about "{topic}" requiring critical thinking and analysis.
Difficulty: {diff_label}
Target university: SLIIT, Sri Lanka — maintain a Sri Lankan academic standard and use local context/examples where applicable.

Return ONLY valid JSON:
{{
    "question": "The essay question here?",
    "model_answer": "Comprehensive model answer with all key points.",
    "correct_answer": "Key themes and arguments to include.",
    "marks_breakdown": {{"accuracy": 30, "completeness": 25, "structure": 20, "terminology": 15, "critical_thinking": 10}}
}}

Rules:
- Phrase the question directly as a real-world scenario or concept. Do NOT refer to "the context", "the document", "the text", "the uploaded material", or "the page".
- CRITICAL DIFFICULTY RULES:
  * HARD: The question MUST be extremely confusing and force the student to rack their brains (user mandaya pottu kulapura mathiri). It should be an indirect, complex scenario at a high Sri Lankan degree standard where the answer requires deep thinking to discover.
  * MEDIUM: The question should be about 15% less hard than the HARD level, but it MUST still be confusing and make the student think deeply to find the answer.
  * EASY: The question MUST be a direct, straightforward question (direct quizes kekanum).
"""


def get_diff_info(score: float) -> Tuple[str, str]:
    """Map difficulty score to (label, bloom_level)."""
    for low, high, label, bloom in DIFF_BANDS:
        if low <= score < high:
            return label, bloom
    return "hard", "evaluate"


def build_blueprint(state: AssessmentState) -> List[dict]:
    """Distribute questions proportionally across topics with randomization to prevent repeats."""
    topics = list(state.get("topics", []) or ["General"])  # fallback if topics is empty
    if not topics:
        topics = ["General"]
    n = state.get("num_questions", 5)
    q_type = state.get("exam_type", "mcq")
    init_diff = INIT_DIFFICULTY.get(state.get("difficulty_mode", "adaptive"), 0.5)

    # Shuffle topics so each session has a different question order
    shuffled_topics = topics[:]
    random.shuffle(shuffled_topics)

    per_topic = max(1, n // len(shuffled_topics))
    remainder = n % len(shuffled_topics)
    blueprint = []

    for i, topic in enumerate(shuffled_topics):
        count = per_topic + (1 if i < remainder else 0)
        for _ in range(count):
            blueprint.append({
                "topic": topic,
                "q_type": q_type,
                "difficulty": init_diff
            })

    # Final shuffle so topic clusters are also mixed
    random.shuffle(blueprint)
    return blueprint[:n]


def quiz_agent(state: AssessmentState) -> dict:
    """
    Quiz Agent.
    - On first call: builds blueprint, generates first question
    - On subsequent calls: generates next question using updated difficulty
    """
    logger.info(f"[QuizAgent] Starting | session={state['session_id']} | "
                f"q_index={state.get('current_q_index', 0)}")

    llm = LlmService()
    rag = RagService()
    grounding = GroundingService()
    logs = list(state.get("agent_logs", []))
    questions = list(state.get("questions", []))
    flagged = list(state.get("flagged_questions", []))

    # Build blueprint on first call
    blueprint = state.get("quiz_blueprint") or []
    if not blueprint:
        blueprint = build_blueprint(state)
        logs.append(f"[QuizAgent] Blueprint created: {len(blueprint)} questions")

    current_idx = state.get("current_q_index", 0)
    if len(questions) > current_idx:
        logs.append(f"[QuizAgent] Question {current_idx+1} already generated. Waiting for correct answer.")
        return {"quiz_blueprint": blueprint, "agent_logs": logs}

    if current_idx >= state.get("num_questions", 5):
        return {"quiz_blueprint": blueprint, "agent_logs": logs}  # All done

    blueprint_item = blueprint[current_idx]
    topic = blueprint_item["topic"]
    diff_score = state.get("current_difficulty",
                           INIT_DIFFICULTY.get(state.get("difficulty_mode", "adaptive"), 0.5))
    diff_label, bloom = get_diff_info(diff_score)
    q_type = state.get("exam_type", "mcq")

    # RAG: retrieve grounded context with randomized query variation to prevent identical questions
    # Build a varied query using topic + bloom level + a random variation keyword
    variation_seeds = [
        "definition", "example", "application", "comparison", "advantage",
        "disadvantage", "mechanism", "process", "purpose", "difference",
        "relationship", "characteristic", "role", "impact", "implementation"
    ]
    variation = random.choice(variation_seeds)
    context_chunks = rag.retrieve(
        collection_id=state["chroma_collection_id"],
        query=f"{topic} {diff_label} {bloom} {variation}",
        k=4
    )

    if not context_chunks:
        logs.append(f"[QuizAgent] No chunks retrieved for topic '{topic}' — using general query")
        context_chunks = rag.retrieve(
            collection_id=state["chroma_collection_id"],
            query=topic,
            k=4
        )

    context_text = "\n\n---\n\n".join([c["text"] for c in context_chunks])

    # Select prompt template
    prompt_map = {"mcq": MCQ_PROMPT, "structured": STRUCTURED_PROMPT, "essay": ESSAY_PROMPT}
    prompt_template = prompt_map.get(q_type, MCQ_PROMPT)
    prompt = prompt_template.format(
        context=context_text,
        topic=topic,
        bloom_level=bloom,
        diff_label=diff_label,
        difficulty=diff_score
    )

    # Generate with retry (tenacity handles this in llm_service)
    # Include previously generated questions to explicitly avoid repetition
    existing_questions = [q["question"] for q in questions]
    no_repeat_instruction = ""
    if existing_questions:
        no_repeat_instruction = (
            "\n\nALREADY GENERATED QUESTIONS (do NOT repeat or paraphrase any of these):\n"
            + "\n".join(f"- {q}" for q in existing_questions)
        )

    q_data = None
    for attempt in range(3):
        try:
            full_prompt = prompt + no_repeat_instruction
            q_data = llm.call_json(full_prompt, temperature=0.5 + random.uniform(0.0, 0.15))
            break
        except (ValueError, Exception) as e:
            logs.append(f"[QuizAgent] JSON parse attempt {attempt+1} failed: {e}")
            if attempt == 2:
                return {
                    "error": f"Question generation failed for topic '{topic}' after 3 attempts.",
                    "quiz_blueprint": blueprint,
                    "agent_logs": logs
                }

    # Grounding check
    g_score = grounding.score(
        generated_text=q_data.get("question", ""),
        source_chunks=[c["text"] for c in context_chunks]
    )

    q_id = str(uuid.uuid4())[:8]
    is_flagged = g_score < float(os.getenv("GROUNDING_THRESHOLD", "0.55"))
    if is_flagged:
        flagged.append(q_id)
        logs.append(f"[QuizAgent] Question {q_id} flagged — grounding={g_score:.3f}")
        # Try once more with k=5
        context_chunks = rag.retrieve(collection_id=state["chroma_collection_id"], query=f"{topic} {bloom}", k=5)
        context_text = "\n\n---\n\n".join([c["text"] for c in context_chunks])
        prompt = prompt_template.format(context=context_text, topic=topic, bloom_level=bloom, diff_label=diff_label, difficulty=diff_score)
        try:
            q_data = llm.call_json(prompt, temperature=0.3)
            g_score = grounding.score(q_data.get("question", ""), [c["text"] for c in context_chunks])
            if g_score >= float(os.getenv("GROUNDING_THRESHOLD", "0.55")):
                flagged.remove(q_id)  # Regeneration succeeded
        except Exception:
            pass  # Keep original

    question_record: QuestionRecord = {
        "q_id":            q_id,
        "topic":           topic,
        "bloom_level":     bloom,
        "difficulty":      diff_score,
        "q_type":          q_type,
        "question":        q_data.get("question", ""),
        "options":         q_data.get("options"),
        "correct_answer":  q_data.get("correct_answer", ""),
        "model_answer":    q_data.get("model_answer", ""),
        "grounding_score": g_score,
        "source_chunk_ids": [c["chunk_id"] for c in context_chunks]
    }

    questions.append(question_record)
    logs.append(f"[QuizAgent] Generated Q{current_idx+1} | topic='{topic}' | "
                f"bloom={bloom} | diff={diff_score:.2f} | grounding={g_score:.3f}")

    logger.info(f"[QuizAgent] Q{current_idx+1} done | grounding={g_score:.3f}")
    return {
        "questions":          questions,
        "quiz_blueprint":     blueprint,
        "flagged_questions":  flagged,
        "current_q_index":   current_idx,
        "current_difficulty": diff_score,
        "agent_logs":         logs
    }
