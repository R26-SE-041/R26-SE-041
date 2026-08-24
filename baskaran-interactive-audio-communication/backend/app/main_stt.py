"""Backward-compatible entry point for the finalized VoiceLearn API.

Existing local launch commands may still reference ``app.main_stt:app``.
They now serve the canonical application without experimental routes.
"""

from app.main import app

__all__ = ["app"]
