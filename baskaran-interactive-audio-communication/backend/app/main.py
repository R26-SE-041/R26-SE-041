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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: run migrations, validate config. Shutdown: flush connections."""
    setup_logging()
    logger = get_logger("startup")
    settings = get_settings()
    logger.info("Starting %s v%s | debug=%s", settings.app_name, settings.app_version, settings.debug)

    # Auto-create Supabase tables + storage buckets (idempotent)
    await run_migrations()
    # Never import the heavy embedding stack during startup unless a complete
    # BGE-M3 cache is already present.  This keeps health and local document
    # management responsive when a download was interrupted.
    bge_ready, bge_reason = bge_m3_cache_status()
    if bge_ready:
        from app.services.ingestion import reindex_stored_documents
        await reindex_stored_documents()
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
