"""Temporary, feature-gated Sinhala transcript -> existing RAG test route."""

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.services.bge_m3_cache import bge_m3_cache_status
from app.services.modal_client import call_localizer, call_rag_generator

logger = get_logger(__name__)
router = APIRouter(prefix="/test", tags=["[TEMP] Sinhala RAG Test"])


class SinhalaRAGTestRequest(BaseModel):
    transcript: str = Field(..., min_length=1)


class SinhalaRAGSource(BaseModel):
    document_id: str
    filename: str
    page: int | None = None
    excerpt: str
    score: float
    retrieval_method: str | None = None


class SinhalaRAGTimings(BaseModel):
    retrieval_ms: int
    generation_ms: int
    localization_ms: int
    total_ms: int


class SinhalaRAGTestResponse(BaseModel):
    transcript: str
    answer: str
    sources: list[SinhalaRAGSource]
    language: str
    retrieval_query: str
    translation_fallback_used: bool
    timings: SinhalaRAGTimings
    latency_ms: int


@router.post("/sinhala-rag", response_model=SinhalaRAGTestResponse)
async def test_sinhala_rag(
    body: SinhalaRAGTestRequest,
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    """Run raw Sinhala Unicode through the existing multilingual RAG stack."""
    settings = get_settings()
    if not settings.use_sinhala_rag_test:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sinhala RAG test endpoint is disabled. "
                "Set USE_SINHALA_RAG_TEST=true and restart the backend."
            ),
        )

    transcript = body.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript cannot be empty")

    bge_ready, reason = bge_m3_cache_status()
    if not bge_ready:
        raise HTTPException(status_code=503, detail=f"BGE-M3 model unavailable: {reason}")

    # Preserve the original Sinhala query: no correction, romanization, or translation.
    query = transcript
    user_id = current_user["sub"] if current_user else "guest"
    total_started = time.perf_counter()

    from app.services.ingestion import hybrid_query_chunks

    retrieval_started = time.perf_counter()
    chunks = await hybrid_query_chunks(query, user_id, n_results=5)
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000)

    if not chunks:
        total_ms = round((time.perf_counter() - total_started) * 1000)
        return SinhalaRAGTestResponse(
            transcript=transcript,
            answer="ඔබ උඩුගත කළ ලේඛනවල මෙම ප්‍රශ්නයට අදාළ තොරතුරු හමු නොවීය.",
            sources=[], language="sinhala", retrieval_query=query,
            translation_fallback_used=False,
            timings=SinhalaRAGTimings(retrieval_ms=retrieval_ms, generation_ms=0, localization_ms=0, total_ms=total_ms),
            latency_ms=total_ms,
        )

    generation_started = time.perf_counter()
    generated = await call_rag_generator(query, [chunk["text"] for chunk in chunks], "sinhala")
    generation_ms = round((time.perf_counter() - generation_started) * 1000)
    answer = generated.get("answer", "")

    localization_started = time.perf_counter()
    localized = await call_localizer(answer, "sinhala")
    localization_ms = round((time.perf_counter() - localization_started) * 1000)
    final_answer = localized.get("localized_text", answer) or answer

    sources = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        text = chunk["text"]
        sources.append(SinhalaRAGSource(
            document_id=str(metadata.get("document_id") or uuid.uuid4()),
            filename=metadata.get("filename", "unknown"), page=metadata.get("page"),
            excerpt=text[:300] + ("…" if len(text) > 300 else ""),
            score=max(0.0, min(1.0, float(chunk.get("score", 0.0)))),
            retrieval_method=chunk.get("retrieval_method"),
        ))

    total_ms = round((time.perf_counter() - total_started) * 1000)
    logger.info(
        "[TEMP SINHALA RAG] user=%s chunks=%d retrieval=%dms generation=%dms localization=%dms total=%dms fallback=false",
        user_id, len(chunks), retrieval_ms, generation_ms, localization_ms, total_ms,
    )
    return SinhalaRAGTestResponse(
        transcript=transcript, answer=final_answer, sources=sources,
        language="sinhala", retrieval_query=query, translation_fallback_used=False,
        timings=SinhalaRAGTimings(retrieval_ms=retrieval_ms, generation_ms=generation_ms, localization_ms=localization_ms, total_ms=total_ms),
        latency_ms=total_ms,
    )
