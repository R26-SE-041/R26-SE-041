"""API v1 router — aggregates all route modules."""

from fastapi import APIRouter

from app.api.v1.routes import auth, documents, voice, sessions

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(documents.router)
router.include_router(voice.router)
router.include_router(sessions.router)

# ── TEMPORARY: Tamil TTS isolated test route ─────────────────────────────────
# Remove these two lines after TTS testing is complete.
# Does NOT affect auth / documents / voice / sessions routes.
from app.api.v1.routes import test_tamil_tts  # noqa: E402
router.include_router(test_tamil_tts.router)
# ── END TEMPORARY ─────────────────────────────────────────────────────────────

# ── TEMPORARY: Sinhala TTS isolated test route ────────────────────────────────
# Remove these two lines after Sinhala TTS evaluation is complete.
# Does NOT affect Tamil/English/Mixed TTS, ASR, RAG, or any production route.
from app.api.v1.routes import test_sinhala_tts  # noqa: E402
router.include_router(test_sinhala_tts.router)

# TEMPORARY: isolated Sinhala transcript -> existing RAG test route.
from app.api.v1.routes import test_sinhala_rag  # noqa: E402
router.include_router(test_sinhala_rag.router)
# ── END TEMPORARY ─────────────────────────────────────────────────────────────
