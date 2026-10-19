"""
FastAPI Application Entry Point.
Adaptive AI Assessment Platform — SLIIT FYP
"""
import os
import logging
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.deployment_config import allowed_origins

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "true").lower() == "true" else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Adaptive Assessment Platform starting...")
    # Pre-compile LangGraph on startup
    from app.graph.graph import get_graph
    get_graph()
    logger.info("✅ LangGraph compiled and ready")
    if os.getenv("PRELOAD_EMBEDDINGS", "true").lower() == "true":
        from app.services.llm_service import EmbeddingService
        started = time.perf_counter()
        logger.info("Loading local embeddings before accepting quiz requests...")
        await asyncio.to_thread(EmbeddingService().get_embedding, "Biology assessment readiness")
        logger.info("[Timing] embedding_startup=%.3fs", time.perf_counter() - started)
    yield
    logger.info("👋 Shutting down...")


app = FastAPI(
    title="Adaptive AI Assessment Platform",
    description="Multi-agent adaptive quiz generation system — MSc Research",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow Next.js dev + prod
ALLOWED_ORIGINS = allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.routers import session, quiz, upload, analytics, documents, history
from app.auth import authorize_request
private = [Depends(authorize_request)]
app.include_router(session.router,   prefix="/api/v1/session",   tags=["Session"], dependencies=private)
app.include_router(upload.router,    prefix="/api/v1/upload",    tags=["Upload"], dependencies=private)
app.include_router(quiz.router,      prefix="/api/v1/quiz",      tags=["Quiz"], dependencies=private)
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"], dependencies=private)
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"], dependencies=private)


@app.get("/")
def root():
    return {
        "message": "Adaptive AI Assessment Platform API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    from app.services.db_service import DbService
    from fastapi import HTTPException
    db = None
    try:
        db = DbService()
        db.conn.execute("SELECT 1 FROM sessions LIMIT 1").fetchall()
    except Exception:
        logger.error("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database unavailable or schema not initialized")
    finally:
        if db is not None and not db.is_postgres:
            db.conn.close()
    return {"status": "ready", "database": "postgresql" if os.getenv("DATABASE_URL") else "sqlite"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "true").lower() == "true"
    )

app.include_router(history.router, prefix="/api/v1/history", tags=["History"], dependencies=private)
