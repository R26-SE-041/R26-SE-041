"""Validated adaptive hint pipeline for Nishy Biology MCQs.

The fine-tuned model is one component of this pipeline. Hints additionally use
quality-gated Biology RAG context, attempt-aware prompting, deterministic safety
and progression validation, retries, and level-specific safe fallbacks.
"""

import logging
import os
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Iterable

from app.services.llm_service import LlmService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)

HINT_LEVELS = ("HARD", "MEDIUM", "EASY")
RAG_MIN_SIMILARITY = float(os.getenv("HINT_RAG_MIN_SIMILARITY", "0.45"))
MAX_RAG_CHUNKS = 3
MAX_CHUNK_CHARS = 900
MAX_PROGRESS_SIMILARITY = 0.72

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "by", "for",
    "from", "has", "have", "how", "in", "is", "it", "its", "of", "on",
    "or", "that", "the", "their", "this", "to", "was", "what", "when",
    "where", "which", "with", "would", "following", "best", "describes",
    "general", "option", "choice", "answer",
}

FORBIDDEN_DIRECT_LANGUAGE = (
    r"\beliminat(?:e|es|ed|ing|ion)\b",
    r"\breject(?:s|ed|ing|ion)?\b",
    r"\brule\s+out\b",
    r"\bremov(?:e|es|ed|ing|al)\b",
)

BIOLOGY_TERMS = {
    "cell", "cellular", "tissue", "organ", "organism", "enzyme", "protein",
    "membrane", "cytoplasm", "nucleus", "dna", "rna", "gene", "genetic",
    "chromosome", "mitosis", "meiosis", "respiration", "photosynthesis",
    "metabolism", "homeostasis", "hormone", "neuron", "ecology", "evolution",
    "species", "plant", "animal", "microorganism", "molecule", "biological",
    "physiology", "anatomy", "transport", "diffusion", "osmosis", "receptor",
    "organelle", "ribosome", "mitochondria", "chloroplast",
}

SAFE_FALLBACKS = (
    (
        "Identify the main biological process tested in the stem, then connect its "
        "function to the relevant structure or mechanism before comparing the choices."
    ),
    (
        "Trace the biological process one step at a time: determine what changes, "
        "where that change occurs, and which mechanism could produce that outcome."
    ),
    (
        "Focus on the immediate structure-to-function relationship described in the "
        "stem, and use that single relationship to make your final comparison."
    ),
)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z0-9-]{2,}", (text or "").casefold())
        if token not in STOPWORDS
    }


def _clean_hint(text: str) -> str:
    """Remove wrappers while preserving readable sentence boundaries."""
    cleaned = re.sub(r"```(?:text)?", "", text or "", flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    cleaned = re.sub(
        r"^\s*(?:level\s*[123]\s*)?(?:hard|medium|easy)?\s*hint\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _is_repetitive_or_malformed(text: str) -> bool:
    """Reject empty, runaway, duplicated, or question-shaped hint output."""
    if len(text) < 30 or len(text) > 700 or "?" in text:
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


def _mentions_option_number(text: str) -> bool:
    """Hints may not refer to numbered choices, even indirectly."""
    return bool(re.search(r"\b[1-5]\b", text or ""))


def _uses_forbidden_language(text: str) -> bool:
    """Reject direct elimination instructions from the tested safety contract."""
    return any(re.search(pattern, text or "", re.IGNORECASE) for pattern in FORBIDDEN_DIRECT_LANGUAGE)


def _correct_answer_terms(question: dict) -> set[str]:
    options = question.get("options") or {}
    answer_key = str(question.get("correct_answer", "")).strip()
    correct_terms = _tokens(str(options.get(answer_key, "")))
    other_terms: set[str] = set()
    for key, value in options.items():
        if str(key) != answer_key:
            other_terms.update(_tokens(str(value)))
    question_terms = _tokens(str(question.get("question", "")))
    # Shared wording and terms already visible in the stem are not leakage.
    # The safety check targets decisive terms unique to the correct choice.
    return correct_terms - other_terms - question_terms


def _reveals_mcq_answer(text: str, question: dict) -> bool:
    """Detect explicit answer disclosure or quotation of the correct choice."""
    answer_key = str(question.get("correct_answer", "")).strip()
    if answer_key:
        key = re.escape(answer_key)
        patterns = (
            rf"\b(?:answer|option|choice)\s*(?:is|:|=)?\s*{key}\b",
            rf"\b(?:choose|select|pick)\s+(?:option\s+)?{key}\b",
            rf"\(\s*{key}\s*\)",
            rf"\*\*\s*{key}\s*\*\*",
        )
        if any(re.search(pattern, text or "", re.IGNORECASE) for pattern in patterns):
            return True

    correct_text = str((question.get("options") or {}).get(answer_key, "")).strip()
    normalized_hint = re.sub(r"\W+", " ", (text or "").casefold()).strip()
    normalized_correct = re.sub(r"\W+", " ", correct_text.casefold()).strip()
    return bool(normalized_correct and normalized_correct in normalized_hint)


def _has_correct_answer_term_overlap(text: str, question: dict) -> bool:
    """Reject decisive terms unique to the correct option before answer reveal."""
    hint_terms = _tokens(text)
    decisive_terms = {
        term for term in _correct_answer_terms(question)
        if len(term) >= 4
    }
    return bool(hint_terms & decisive_terms)


def _progression_similarity(text: str, previous_hints: Iterable[str]) -> float:
    """Return maximum lexical/sequence similarity to any earlier hint."""
    normalized = " ".join(sorted(_tokens(text)))
    current_terms = _tokens(text)
    maximum = 0.0
    for previous in previous_hints:
        previous_terms = _tokens(previous)
        union = current_terms | previous_terms
        jaccard = len(current_terms & previous_terms) / len(union) if union else 1.0
        previous_normalized = " ".join(sorted(previous_terms))
        sequence = SequenceMatcher(None, normalized, previous_normalized).ratio()
        maximum = max(maximum, jaccard, sequence)
    return maximum


def _has_meaningful_progression(text: str, previous_hints: list[str], hint_level: int) -> bool:
    if hint_level == 0 or not previous_hints:
        return True
    if _progression_similarity(text, previous_hints) >= MAX_PROGRESS_SIMILARITY:
        return False
    current_terms = _tokens(text)
    previous_terms = set().union(*(_tokens(hint) for hint in previous_hints))
    new_terms = current_terms - previous_terms
    return len(new_terms) >= max(3, len(current_terms) // 4)


def _is_question_relevant(text: str, question: dict) -> bool:
    """Require the hint to stay tied to the MCQ's biological subject matter."""
    reference = " ".join((
        str(question.get("question", "")),
        str(question.get("topic", "")),
        str(question.get("model_answer", "")),
    ))
    reference_terms = _tokens(reference) - _correct_answer_terms(question)
    hint_terms = _tokens(text)
    overlap = hint_terms & reference_terms
    return len(overlap) >= 1 or len(hint_terms & BIOLOGY_TERMS) >= 2


def _validate_hint(
    hint: str,
    question: dict,
    hint_level: int,
    previous_hints: list[str],
) -> list[str]:
    """Return all safety, relevance, and progression rejection reasons."""
    reasons = []
    if _is_repetitive_or_malformed(hint):
        reasons.append("malformed_or_repetitive")
    if _mentions_option_number(hint):
        reasons.append("option_number")
    if _uses_forbidden_language(hint):
        reasons.append("direct_elimination_language")
    if _reveals_mcq_answer(hint, question):
        reasons.append("correct_answer_leakage")
    if _has_correct_answer_term_overlap(hint, question):
        reasons.append("correct_answer_term_overlap")
    if not _is_question_relevant(hint, question):
        reasons.append("question_type_relevance")
    if not _has_meaningful_progression(hint, previous_hints, hint_level):
        reasons.append("progression_similarity")
    return reasons


def _select_relevant_biology_chunks(chunks: list[dict], question: dict) -> list[dict]:
    """Keep only semantically relevant Biology retrieval results."""
    query_terms = _tokens(f"{question.get('topic', '')} {question.get('question', '')}")
    selected = []
    for chunk in chunks:
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue
        distance = chunk.get("distance")
        if distance is None:
            continue
        similarity = 1.0 - float(distance)
        text_terms = _tokens(text)
        lexical_match = bool(query_terms & text_terms)
        biology_match = bool(text_terms & BIOLOGY_TERMS)
        if similarity < RAG_MIN_SIMILARITY:
            continue
        if not biology_match and not lexical_match and similarity < RAG_MIN_SIMILARITY + 0.15:
            continue
        selected.append(chunk)
        if len(selected) >= MAX_RAG_CHUNKS:
            break
    return selected


def _retrieve_biology_context(rag: RagService, collection_id: str, question: dict) -> str:
    query = f"{question.get('topic', '')} {question.get('question', '')}".strip()
    try:
        chunks = rag.retrieve(collection_id, query, k=5)
    except Exception as exc:
        logger.error("Hint context retrieval failed: %s", exc)
        return ""
    selected = _select_relevant_biology_chunks(chunks, question)
    logger.info(
        "Hint RAG selected %d/%d chunks | min_similarity=%.2f",
        len(selected),
        len(chunks),
        RAG_MIN_SIMILARITY,
    )
    return "\n\n---\n\n".join(
        str(chunk["text"])[:MAX_CHUNK_CHARS] for chunk in selected
    )


def _build_hint_prompt(
    question: dict,
    hint_level: int,
    context: str,
    previous_hints: list[str],
) -> str:
    level = HINT_LEVELS[min(max(hint_level, 0), 2)]
    level_instruction = (
        "Give a subtle Socratic conceptual direction that forces reasoning. Do not apply the decisive fact to this exact case.",
        "Narrow the reasoning by exactly one meaningful biological mechanism or relationship beyond HARD, without deciding the answer.",
        "Focus one biological step more than MEDIUM and state how to reason through that step, while leaving the final decision to the learner.",
    )[hint_level]
    context_block = (
        f"Relevant Biology resource context (use only if helpful):\n{context}"
        if context
        else "No sufficiently relevant Biology resource context was retrieved."
    )
    history_block = "\n".join(
        f"Earlier {HINT_LEVELS[index]} hint: {hint}"
        for index, hint in enumerate(previous_hints)
    ) or "No earlier hints."
    return f"""You are the Nishy adaptive Biology hint tutor.
Question: {question.get('question', '')}
Topic: {question.get('topic', '')}
Hint level: {level}

{context_block}

Earlier hints:
{history_block}

Task: {level_instruction}
Safety rules:
- Return only one concise hint of 35-60 words; no heading, preamble, or question.
- Do not reveal the answer, mention any option number, or quote/paraphrase an answer choice.
- Do not use the words eliminate, reject, rule out, or remove.
- Do not expose the decisive biological fact early.
- Do not repeat wording or reasoning already used in earlier hints.
- Stay directly relevant to the biological process tested by the question.
"""


def generate_adaptive_hint(
    llm: LlmService,
    rag: RagService,
    question: dict,
    hint_level: int,
    collection_id: str,
    previous_hints: list[str] | None = None,
) -> str:
    """Generate and validate HARD/MEDIUM/EASY hints with safe fallback."""
    level = min(max(hint_level, 0), 2)
    history = list(previous_hints or [])[:level]

    # A cold/unavailable Modal worker used to make the learner wait for three
    # full inference timeouts before receiving this same validated fallback.
    # Keep the hint contract unchanged while failing over in about three seconds.
    try:
        if hasattr(llm, "check_health") and not llm.check_health():
            logger.warning("Hint model unavailable; using safe %s fallback immediately", HINT_LEVELS[level])
            return SAFE_FALLBACKS[level]
    except Exception as exc:
        logger.warning("Hint health check failed (%s); using safe fallback", exc)
        return SAFE_FALLBACKS[level]

    context = _retrieve_biology_context(rag, collection_id, question)
    base_prompt = _build_hint_prompt(question, level, context, history)

    rejection_reasons: list[str] = []
    for attempt in range(3):
        retry = ""
        if attempt:
            retry = (
                "\nPrevious candidate failed validation for: "
                + ", ".join(rejection_reasons)
                + ". Produce a materially different safe hint."
            )
        try:
            hint = _clean_hint(llm.call(base_prompt + retry))
            rejection_reasons = _validate_hint(hint, question, level, history)
            if not rejection_reasons:
                logger.info("Accepted %s hint on generation attempt %d", HINT_LEVELS[level], attempt + 1)
                return hint
            logger.warning(
                "Rejected %s hint | attempt=%d | reasons=%s",
                HINT_LEVELS[level],
                attempt + 1,
                ",".join(rejection_reasons),
            )
        except Exception as exc:
            rejection_reasons = ["model_error"]
            logger.error("%s hint generation failed on attempt %d: %s", HINT_LEVELS[level], attempt + 1, exc)

    logger.warning("Using safe %s fallback hint", HINT_LEVELS[level])
    return SAFE_FALLBACKS[level]
