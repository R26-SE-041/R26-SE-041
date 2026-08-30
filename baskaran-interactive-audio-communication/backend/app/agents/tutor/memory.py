"""Small in-process, TTL-limited memento store for Tutor follow-ups."""

from __future__ import annotations

import time
import re
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)
_TTL_SECONDS = 30 * 60
_MAX_TEXT_LENGTH = 480
ALLOWED_MEMORY_FIELDS = frozenset(
    {
        "language",
        "document_ids",
        "topic",
        "previous_question",
        "previous_answer_summary",
        "rag_source_references",
    }
)
_FOLLOW_UP_PATTERN = re.compile(
    r"\b(?:it|this|that|above|previous|why)\b|explain more|what about|how does",
    re.IGNORECASE,
)


@dataclass
class TutorMemento:
    language: str
    document_ids: list[str]
    topic: str | None
    previous_question: str
    previous_answer_summary: str
    rag_source_references: list[str]
    updated_at: float


_sessions: dict[str, TutorMemento] = {}


def _short_text(value: str) -> str:
    return " ".join(value.split())[:_MAX_TEXT_LENGTH]


def _is_related_follow_up(question: str) -> bool:
    return bool(_FOLLOW_UP_PATTERN.search(question))


def filter_allowed_memory_fields(fields: dict) -> dict:
    """Remove fields not permitted by memento.md, including sensitive values."""
    return {key: value for key, value in fields.items() if key in ALLOWED_MEMORY_FIELDS}


def contextual_retrieval_query(question: str, memento: dict | None) -> str:
    """Resolve an explicit follow-up for retrieval without altering the visible question."""
    if not memento:
        return question
    previous_question = str(memento.get("previous_question") or "").strip()
    return f"{previous_question} {question}".strip() if previous_question else question


def get_relevant_memento(session_id: str | None, question: str) -> dict | None:
    """Return only a previous turn for an explicit related follow-up."""
    if not session_id:
        return None
    entry = _sessions.get(session_id)
    if not entry or time.monotonic() - entry.updated_at > _TTL_SECONDS:
        _sessions.pop(session_id, None)
        return None
    if not _is_related_follow_up(question):
        logger.debug("Tutor session memory not used: question is not a follow-up")
        return None
    logger.debug("Tutor session memory used for a related follow-up")
    return filter_allowed_memory_fields({
        "language": entry.language,
        "document_ids": entry.document_ids,
        "topic": entry.topic,
        "previous_question": entry.previous_question,
        "previous_answer_summary": entry.previous_answer_summary,
        "rag_source_references": entry.rag_source_references,
    })


def update_memento(
    session_id: str | None, *, language: str, document_ids: list[str], question: str, answer: str
) -> None:
    """Replace, rather than append to, the short-lived session memento."""
    if not session_id:
        return
    _sessions[session_id] = TutorMemento(
        language=language,
        document_ids=document_ids[:5],
        topic=None,
        previous_question=_short_text(question),
        previous_answer_summary=_short_text(answer),
        rag_source_references=document_ids[:5],
        updated_at=time.monotonic(),
    )
