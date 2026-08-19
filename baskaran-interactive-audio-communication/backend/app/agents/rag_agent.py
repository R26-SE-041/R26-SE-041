"""
RAG Generation Agent — LangGraph node (Phase 2).

Responsibility: Retrieve relevant chunks from ChromaDB and generate
a grounded answer using Llama 3.1 8B Instruct on Modal.
"""

from app.services.modal_client import call_rag_generator
from app.core.logging import get_logger

logger = get_logger(__name__)


async def rag_agent_node(state: dict) -> dict:
    """
    LangGraph node: Retrieval-Augmented Generation.

    Expected state keys in:
        enhanced_query (str): Query to retrieve against.
        user_id (str): For user-scoped ChromaDB retrieval.
        language (str): Answer language.

    State keys out:
        chunks (list[dict]): Retrieved context chunks.
        answer (str): Generated answer grounded in retrieved context.
    """
    query: str = state.get("enhanced_query") or state.get("transcript", "")
    user_id: str = state.get("user_id", "")
    language: str = state.get("language", "english")

    logger.info("RAG agent: retrieving chunks for user=%s", user_id)

    # Keep the embedding runtime out of application startup.  Upload routes
    # preflight BGE-M3 before importing it; retrieval reaches it only when a
    # real RAG request is made.
    from app.services.ingestion import hybrid_query_chunks

    chunks = await hybrid_query_chunks(query, user_id)
    context_texts = [c["text"] for c in chunks]

    result = await call_rag_generator(query, context_texts, language)

    return {
        **state,
        "chunks": chunks,
        "answer": result.get("answer", "I could not find an answer in the provided documents."),
    }
