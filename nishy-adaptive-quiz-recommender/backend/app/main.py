"""
FastAPI Application Entry Point.
Adaptive AI Assessment Platform — SLIIT FYP
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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
    yield
    logger.info("👋 Shutting down...")


app = FastAPI(
    title="Adaptive AI Assessment Platform",
    description="Multi-agent adaptive quiz generation system — MSc Research",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow Next.js dev + prod
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.routers import session, quiz, upload, analytics, documents
app.include_router(session.router,   prefix="/api/v1/session",   tags=["Session"])
app.include_router(upload.router,    prefix="/api/v1/upload",    tags=["Upload"])
app.include_router(quiz.router,      prefix="/api/v1/quiz",      tags=["Quiz"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "true").lower() == "true"
    )
