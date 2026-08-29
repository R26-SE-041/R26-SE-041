"""
FastAPI application factory.

Lifespan context manager handles startup/shutdown tasks cleanly
(no deprecated `on_event` hooks).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.migrations import run_migrations
from app.services.bge_m3_cache import bge_m3_cache_status
from app.agents.tutor.config import load_tutor_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: run migrations, validate config. Shutdown: flush connections."""
    setup_logging()
    logger = get_logger("startup")
    settings = get_settings()
    logger.info("Starting %s v%s | debug=%s", settings.app_name, settings.app_version, settings.debug)
    load_tutor_config()

    # Auto-create Supabase tables + storage buckets (idempotent)
    await run_migrations()
    # Never import the heavy embedding stack during startup unless a complete
    # BGE-M3 cache is already present.  This keeps health and local document
    # management responsive when a download was interrupted.
    bge_ready, bge_reason = bge_m3_cache_status()
    if bge_ready:
        if settings.chroma_host in {"localhost", "127.0.0.1", "local"}:
            from app.db.chroma import persistent_index_status
            from app.services.local_document_store import list_all_documents

            stored_document_ids = {
                str(record["document_id"]) for record in list_all_documents()
            }
            index_valid, chunk_count, missing_document_ids = await persistent_index_status(
                stored_document_ids
            )
            if index_valid:
                logger.info(
                    "Existing Chroma index detected: chunks=%d stored_documents=%d",
                    chunk_count,
                    len(stored_document_ids),
                )
                logger.info("Reusing persistent index; full reindex skipped")
            else:
                logger.info(
                    "Reindex required: %d stored document(s) missing from Chroma",
                    len(missing_document_ids),
                )
                from app.services.ingestion import reindex_stored_documents
                await reindex_stored_documents()
                logger.info("Reindex completed")
        else:
            from app.services.ingestion import reindex_stored_documents
            logger.info("Reindex required: validating remote persistent document sources")
            await reindex_stored_documents()
            logger.info("Reindex completed")
        logger.info("RAG service initialized")
    else:
        logger.warning("BGE-M3 reindex skipped: %s", bge_reason)

    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,  # Hide docs in prod
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
