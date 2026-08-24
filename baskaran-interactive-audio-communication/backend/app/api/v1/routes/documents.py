"""
Document management routes.

POST   /api/v1/documents/upload         — Upload & ingest any supported document
GET    /api/v1/documents                — List user's documents
DELETE /api/v1/documents/{doc_id}       — Delete a document + its storage file
POST   /api/v1/documents/ask            — Ask a question (Prompt Enhance → RAG)

Supported file types: .pdf, .pptx, .docx, .xlsx, .txt, .md

NOTE: When Supabase is not configured (placeholder creds), documents are stored
      in an in-memory registry and indexed into ChromaDB. This is the local dev
      mode — everything works except persistent cross-restart storage.
"""

import asyncio
import pathlib
import time
import uuid
from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.security import get_current_user
from app.services.modal_client import call_transcript_corrector, call_rag_generator, call_localizer
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentListItem,
    ChunkReference,
    AskRequest,
    AskResponse,
    EnhanceRequest,
    EnhanceResponse,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services import local_document_store
from app.services.bge_m3_cache import bge_m3_cache_status

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# ── In-memory document registry (local dev fallback) ─────────────────────────
# Structure: { user_id: { doc_id: {filename, file_type, chunk_count, uploaded_at} } }
def _is_supabase_configured() -> bool:
    """Return True only for configured non-local deployments.

    Local development already has the SQLite/file persistence fallback.  Avoid
    making a user-facing upload or list request depend on an unreachable
    remote Supabase instance when CHROMA_HOST selects the local stack.
    """
    settings = get_settings()
    return (
        settings.chroma_host not in {"localhost", "127.0.0.1", "local"}
        and
        settings.supabase_url != ""
        and "placeholder" not in settings.supabase_url.lower()
        and "placeholder" not in settings.supabase_service_role_key.lower()
    )


async def _try_supabase_insert(document_id: str, user_id: str, filename: str,
                                file_type: str, storage_path: str, chunk_count: int) -> None:
    """Try to insert into Supabase DB — silently skip if not configured."""
    try:
        from app.db.supabase import get_supabase
        async def insert():
            client = await get_supabase()
            await client.table("documents").insert({
                "id": document_id,
                "user_id": user_id,
                "filename": filename,
                "file_type": file_type,
                "storage_path": storage_path,
                "chunk_count": chunk_count,
            }).execute()

        await asyncio.wait_for(
            insert(),
            timeout=get_settings().supabase_request_timeout_seconds,
        )
    except Exception as e:
        logger.warning("Supabase DB insert skipped (not configured): %s", e)


async def _try_supabase_storage(user_id: str, filename: str, content: bytes) -> str:
    """Try to upload to Supabase Storage — return empty string if not configured."""
    try:
        from app.services.storage import upload_document
        path = await asyncio.wait_for(
            upload_document(user_id, filename, content),
            timeout=get_settings().supabase_request_timeout_seconds,
        )
        return path
    except Exception as e:
        logger.warning("Supabase Storage upload skipped (not configured): %s", e)
        return ""


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_endpoint(
    file: Annotated[UploadFile, File(description="Lecture document (PDF, PPTX, DOCX, XLSX, TXT, MD)")],
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    """
    Upload a document and index it into ChromaDB.
    Works without Supabase — uses in-memory local registry as fallback.
    """
    settings = get_settings()
    bge_ready, bge_reason = bge_m3_cache_status()
    if not bge_ready:
        logger.error("Upload rejected: BGE-M3 cache check failed: %s", bge_reason)
        raise HTTPException(
            status_code=503,
            detail=(
                "BGE-M3 model unavailable: local cache is incomplete or corrupt, so indexing "
                "is unavailable. Complete the BAAI/bge-m3 model setup and retry."
            ),
        )
    # Load the expensive embedding implementation only for an actual upload;
    # document listing and deletion must remain available independently.
    from app.services.ingestion import (
        DocumentIngestionError,
        DocumentIngestionTimeoutError,
        SUPPORTED_EXTENSIONS,
        ingest_document,
    )

    # Validate extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = pathlib.Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    content = await file.read()

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_mb} MB limit",
        )

    user_id = current_user["sub"] if current_user else "guest"
    document_id = str(uuid.uuid4())
    file_type = ext.lstrip(".")
    now = datetime.now(timezone.utc)

    # 1. Extract text + embed + upsert into ChromaDB (always happens)
    try:
        chunk_count = await ingest_document(content, document_id, file.filename, user_id)
    except DocumentIngestionTimeoutError as exc:
        logger.error("Document upload timed out during ingestion: file=%s", file.filename)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except DocumentIngestionError as exc:
        # Never show a successful upload with an unusable "0 chunks indexed"
        # status.  The user can immediately choose a text-searchable file.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to ingest document %s", file.filename)
        raise HTTPException(
            status_code=422,
            detail=f"Could not read and index '{file.filename}'. Please try another supported file.",
        ) from exc

    # 2. Store original file. Prefer Supabase, otherwise persist it locally.
    storage_path = ""
    if _is_supabase_configured():
        storage_path = await _try_supabase_storage(user_id, file.filename, content)
    if not storage_path:
        storage_path = local_document_store.save_document(
            document_id=document_id,
            user_id=user_id,
            filename=file.filename,
            file_type=file_type,
            chunk_count=chunk_count,
            uploaded_at=now,
            content=content,
        )

    # 3. Try Supabase DB insert (graceful fallback)
    await _try_supabase_insert(document_id, user_id, file.filename, file_type, storage_path, chunk_count)

    logger.info("Document %s (%s) ingested: %d chunks [user=%s]", document_id, file_type, chunk_count, user_id)

    return DocumentUploadResponse(
        document_id=uuid.UUID(document_id),
        filename=file.filename,
        file_type=file_type,
        storage_path=storage_path,
        chunk_count=chunk_count,
        uploaded_at=now,
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[DocumentListItem])
async def list_documents(
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    """Return all documents uploaded by the current user."""
    user_id = current_user["sub"] if current_user else "guest"

    # Try Supabase first if configured
    if _is_supabase_configured():
        try:
            from app.db.supabase import get_supabase
            async def fetch():
                client = await get_supabase()
                return await (
                    client.table("documents")
                    .select("*")
                    .eq("user_id", user_id)
                    .order("created_at", desc=True)
                    .execute()
                )

            result = await asyncio.wait_for(
                fetch(),
                timeout=get_settings().supabase_request_timeout_seconds,
            )
            return [
                DocumentListItem(
                    document_id=uuid.UUID(row["id"]),
                    filename=row["filename"],
                    file_type=row.get("file_type", "pdf"),
                    chunk_count=row["chunk_count"],
                    uploaded_at=row["created_at"],
                )
                for row in result.data
            ]
        except Exception as e:
            logger.warning("Supabase list failed, using local registry: %s", e)

    # Fallback: persistent local registry.
    user_docs = local_document_store.list_documents(user_id)
    return [
        DocumentListItem(
            document_id=uuid.UUID(meta["document_id"]),
            filename=meta["filename"],
            file_type=meta["file_type"],
            chunk_count=meta["chunk_count"],
            uploaded_at=meta["uploaded_at"],
        )
        for meta in user_docs
    ]


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    """Delete document from local registry + ChromaDB. Supabase cleanup is best-effort."""
    user_id = current_user["sub"] if current_user else "guest"

    # Check local registry first
    local_record = local_document_store.get_document(document_id, user_id)
    storage_path = local_record.get("storage_path") if local_record else None

    if local_record:
        logger.info("Preparing local document %s for deletion", document_id)
    if _is_supabase_configured():
        # Try Supabase as source of truth
        try:
            from app.db.supabase import get_supabase
            client = await get_supabase()
            fetch = (
                await client.table("documents")
                .select("storage_path")
                .eq("id", document_id)
                .eq("user_id", user_id)
                .execute()
            )
            if fetch.data:
                storage_path = fetch.data[0]["storage_path"]
                await client.table("documents").delete().eq("id", document_id).eq(
                    "user_id", user_id
                ).execute()
            elif not local_record:
                raise HTTPException(status_code=404, detail="Document not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Supabase delete failed: %s", e)
            raise HTTPException(status_code=404, detail="Document not found")
    else:
        # Local-dev mode: doc may have been lost after server restart.
        # Best-effort: still clean up ChromaDB and return 204 (idempotent delete).
        logger.warning(
            "Doc %s not in local registry (server may have restarted) — "
            "cleaning up ChromaDB and returning 204",
            document_id,
        )

    # Delete from Supabase Storage (non-fatal)
    if storage_path and not storage_path.startswith("local/"):
        try:
            from app.services.storage import delete_document_file
            await delete_document_file(storage_path)
        except Exception as e:
            logger.warning("Could not delete storage file %s: %s", storage_path, e)

    # Remove embeddings before the local registry so a failed Chroma operation
    # leaves the document visible and retryable instead of orphaning its chunks.
    try:
        from app.db.chroma import get_or_create_collection
        collection = await get_or_create_collection()
        await collection.delete(where={"document_id": document_id})
        logger.info("Deleted ChromaDB chunks for doc %s", document_id)
    except Exception as e:
        logger.exception("Could not delete ChromaDB chunks for doc %s", document_id)
        raise HTTPException(status_code=500, detail="Could not delete document index. Please retry.") from e

    if local_record:
        local_document_store.delete_document(document_id, user_id)
        logger.info("Deleted local document file and metadata for %s", document_id)


# ── Enhance (Phase 2 — prompt enhancement only) ──────────────────────────────

@router.post("/enhance", response_model=EnhanceResponse)
async def enhance_query(
    body: EnhanceRequest,
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    """
    Correct a raw ASR transcript via Gemma 4 12B IT (user-triggered only).
    Fixes obvious ASR errors while preserving the speaker's original meaning.
    Returns the corrected transcript for the user to review before asking.
    """
    transcript = body.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript cannot be empty")

    try:
        result = await call_transcript_corrector(transcript, body.language)
        corrected = result.get("corrected_transcript", transcript)
    except Exception as e:
        logger.warning("Transcript corrector failed, returning raw transcript: %s", e)
        corrected = transcript

    return EnhanceResponse(enhanced_query=corrected or transcript)


# ── Ask (Phase 2 RAG pipeline) ────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
async def ask_question(
    body: AskRequest,
    current_user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    """
    Phase 2 RAG pipeline:
    1. Query selection -- uses corrected_transcript if frontend provides it
       (user chose 'Fix Transcript'); otherwise uses raw transcript directly.
       Gemma is NEVER called automatically here.
    2. Retrieve top-5 relevant chunks from ChromaDB (user-scoped)
    3. Generate a grounded answer via Gemma 4 12B in the selected language
       (or use the legacy English + Localizer path when the experiment is off)
    4. Return the final answer + source references
    """
    rag_started = time.perf_counter()
    bge_ready, _ = bge_m3_cache_status()
    if not bge_ready:
        raise HTTPException(
            status_code=503,
            detail="BGE-M3 model unavailable: local cache is incomplete or corrupt.",
        )
    from app.services.ingestion import hybrid_query_chunks

    user_id = current_user["sub"] if current_user else "guest"
    transcript = body.transcript.strip()
    language = body.language
    direct_multilingual_gemma = get_settings().use_direct_multilingual_gemma

    if not transcript:
        raise HTTPException(status_code=400, detail="transcript cannot be empty")

    # Step 1 -- Query selection (no model call)
    if body.enhanced_query and body.enhanced_query.strip():
        query = body.enhanced_query.strip()
        logger.info("Ask: using corrected transcript from frontend")
    else:
        query = transcript
        logger.info("Ask: using raw transcript directly")

    # Step 2 -- BGE-M3 dense retrieval + BM25 keyword signals + multilingual reranking.
    retrieval_started = time.perf_counter()
    raw_chunks = await hybrid_query_chunks(query, user_id, n_results=5)
    logger.info("[LATENCY] RETRIEVAL = %.3fs", time.perf_counter() - retrieval_started)

    if not raw_chunks:
        no_content_messages = {
            "tamil": "பதிவேற்றிய ஆவணங்களில் இந்தக் கேள்விக்கான தொடர்புடைய தகவல் கிடைக்கவில்லை. முதலில் வாசிக்கக்கூடிய lecture document ஒன்றைப் பதிவேற்றவும்.",
            "sinhala": "ඔබ උඩුගත කළ ලේඛනවල මෙම ප්‍රශ්නයට අදාළ තොරතුරු හමු නොවීය. කරුණාකර කියවිය හැකි lecture document එකක් උඩුගත කරන්න.",
        }
        response = AskResponse(
            answer=no_content_messages.get(
                language,
                "I couldn't find relevant content in your uploaded documents. Please upload lecture materials first.",
            ),
            enhanced_query=query,
            references=[],
        )
        logger.info("[LATENCY] RAG TOTAL = %.3fs", time.perf_counter() - rag_started)
        return response

    # Step 3 — RAG generation. The flag keeps the legacy English-first path
    # immediately restorable without duplicating retrieval or generation.
    context_texts = [c["text"] for c in raw_chunks]
    rag_language = language if direct_multilingual_gemma else "english"
    logger.info(
        "[RAG] direct_multilingual_gemma=%s language=%s",
        str(direct_multilingual_gemma).lower(),
        language,
    )
    gemma_started = time.perf_counter()
    try:
        rag_result = await call_rag_generator(query, context_texts, rag_language)
        answer = rag_result.get("answer", "I couldn't generate an answer right now.")
        remote_timings = rag_result.get("timings_ms") or {}
        logger.info(
            "[LATENCY] GEMMA REMOTE tokenize_ms=%s generation_ms=%s total_ms=%s "
            "input_tokens=%s output_tokens=%s",
            remote_timings.get("tokenize"),
            remote_timings.get("generation"),
            remote_timings.get("total"),
            rag_result.get("input_tokens"),
            rag_result.get("output_tokens"),
        )
    except Exception as e:
        logger.error("RAG generator failed: %s", e)
        answer = "RAG generation is not available right now. Please deploy the Modal RAG endpoint."
    finally:
        logger.info("[LATENCY] GEMMA = %.3fs", time.perf_counter() - gemma_started)

    # Step 4 — Legacy localization. Direct mode returns Gemma's selected-language
    # answer unchanged and deliberately has no hidden quality-triggered fallback.
    if not direct_multilingual_gemma and language != "english":
        try:
            localizer_started = time.perf_counter()
            loc_result = await call_localizer(answer, language)
            localized_answer = loc_result.get("localized_text", answer)
            logger.info(
                "Ask: localized %d → %d chars (lang=%s)",
                len(answer),
                len(localized_answer),
                language,
            )
        except Exception as e:
            # Never crash the pipeline — fallback to English answer
            logger.warning("Localizer failed, returning English answer: %s", e)
            localized_answer = answer
        finally:
            logger.info(
                "[LATENCY] LOCALIZER language=%s = %.3fs",
                language,
                time.perf_counter() - localizer_started,
            )
    else:
        localized_answer = answer

    # Step 5 — Build source references
    references = []
    for idx, chunk in enumerate(raw_chunks):
        meta = chunk.get("metadata", {})
        try:
            references.append(
                ChunkReference(
                    document_id=uuid.UUID(meta.get("document_id", str(uuid.uuid4()))),
                    filename=meta.get("filename", "unknown"),
                    chunk_index=idx,
                    page=meta.get("page"),
                    excerpt=chunk["text"][:200] + ("…" if len(chunk["text"]) > 200 else ""),
                    score=chunk.get("score", 0.0),
                )
            )
        except Exception:
            pass  # Skip malformed references

    logger.info(
        "Ask: user=%s, lang=%s, chunks=%d, answer_len=%d",
        user_id, language, len(references), len(localized_answer),
    )

    response = AskResponse(
        answer=localized_answer,
        enhanced_query=query,
        references=references,
    )
    logger.info("[LATENCY] RAG TOTAL = %.3fs", time.perf_counter() - rag_started)
    return response
