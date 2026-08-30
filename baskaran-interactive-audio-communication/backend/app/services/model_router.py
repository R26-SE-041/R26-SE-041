"""Deterministic, credit-safe routing for VoiceLearn answer generation."""

from __future__ import annotations

from dataclasses import dataclass
import re


DOCUMENT_RAG_BASE = "document_rag_base"
MUSCLE_FINETUNED_V2 = "muscle_finetuned_v2"
GENERAL_BASE = "general_base"

_MUSCLE_PATTERN = re.compile(
    r"\b(?:pectoralis(?:\s+major)?|deltoid|biceps(?:\s+brachii)?|"
    r"triceps(?:\s+brachii)?|quadriceps(?:\s+femoris)?)\b",
    re.IGNORECASE,
)
_NEW_TOPIC_PATTERN = re.compile(
    r"^\s*(?:new\s+topic|topic\s+change|switch\s+topic)\s*[:,-]?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteDecision:
    name: str
    reason: str


def is_five_muscle_question(question: str) -> bool:
    """Match only the five LoRA-trained muscle domains and their normal variants."""
    return bool(_MUSCLE_PATTERN.search(question))


def choose_answer_route(
    question: str,
    *,
    document_grounded: bool,
    memento: dict | None = None,
) -> RouteDecision:
    """Select a route without retrieval or a model call.

    A document request always wins.  A short-lived memento can resolve an
    explicit follow-up only; it cannot turn a clearly new topic into anatomy.
    """
    if document_grounded:
        return RouteDecision(DOCUMENT_RAG_BASE, "explicit_document_context")

    if is_five_muscle_question(question):
        return RouteDecision(MUSCLE_FINETUNED_V2, "five_muscle_match")

    previous_question = str((memento or {}).get("previous_question") or "")
    if (
        memento
        and not _NEW_TOPIC_PATTERN.search(question)
        and is_five_muscle_question(previous_question)
    ):
        return RouteDecision(MUSCLE_FINETUNED_V2, "muscle_followup_from_session")

    return RouteDecision(GENERAL_BASE, "general_query")
