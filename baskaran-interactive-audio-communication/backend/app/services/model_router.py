"""Select document retrieval or the base answer service without topic routing."""
from dataclasses import dataclass

DOCUMENT_RAG_BASE = "document_rag_base"
GENERAL_BASE = "general_base"


@dataclass(frozen=True)
class RouteDecision:
    name: str
    reason: str


def choose_answer_route(
    question: str, *, document_grounded: bool, memento: dict | None = None,
) -> RouteDecision:
    """Document requests use retrieval; other requests use the base model.

    Topic text and old session memory never select a specialized model.
    """
    if document_grounded:
        return RouteDecision(DOCUMENT_RAG_BASE, "explicit_document_context")
    return RouteDecision(GENERAL_BASE, "general_query")
