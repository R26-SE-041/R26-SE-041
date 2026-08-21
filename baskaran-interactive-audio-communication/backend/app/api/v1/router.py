"""Canonical API v1 router for the final VoiceLearn workflow."""

from fastapi import APIRouter

from app.api.v1.routes import auth, documents, sessions, voice

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(documents.router)
router.include_router(voice.router)
router.include_router(sessions.router)
