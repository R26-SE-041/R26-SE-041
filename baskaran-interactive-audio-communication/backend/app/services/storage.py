"""
Supabase Storage service.
Handles secure file uploads and signed URL generation.
Supports all document formats: PDF, PPTX, DOCX, XLSX, TXT, MD.
"""

import pathlib
import uuid
from app.db.supabase import get_supabase
from app.core.logging import get_logger

logger = get_logger(__name__)

BUCKET = "documents"

# Map extension → MIME type
_MIME_TYPES: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt":  "text/plain",
    ".md":   "text/markdown",
}


def _content_type(filename: str) -> str:
    ext = pathlib.Path(filename).suffix.lower()
    return _MIME_TYPES.get(ext, "application/octet-stream")


async def upload_document(user_id: str, filename: str, content: bytes) -> str:
    """
    Upload any supported document to Supabase Storage.

    Returns the storage path (used as a reference, not a public URL).
    Path format: {user_id}/{uuid}/{filename}
    """
    client = await get_supabase()
    path = f"{user_id}/{uuid.uuid4()}/{filename}"
    mime = _content_type(filename)
    await client.storage.from_(BUCKET).upload(path, content, {"content-type": mime})
    logger.info("Uploaded %s (%s) to %s", filename, mime, path)
    return path


async def get_signed_url(path: str, expires_in: int = 3600) -> str:
    """Return a short-lived signed URL for a stored file."""
    client = await get_supabase()
    result = await client.storage.from_(BUCKET).create_signed_url(path, expires_in)
    return result["signedURL"]


async def delete_document_file(path: str) -> None:
    """Delete a file from Supabase Storage."""
    client = await get_supabase()
    await client.storage.from_(BUCKET).remove([path])
    logger.info("Deleted storage file: %s", path)


async def download_document(path: str) -> bytes:
    """Download an original upload so it can be re-embedded after a model upgrade."""
    client = await get_supabase()
    return await client.storage.from_(BUCKET).download(path)


async def upload_audio(session_id: str, audio_bytes: bytes) -> str:
    """Upload TTS audio output and return its storage path."""
    client = await get_supabase()
    path = f"audio/{session_id}/{uuid.uuid4()}.wav"
    await client.storage.from_("audio").upload(path, audio_bytes, {"content-type": "audio/wav"})
    return path


# Backwards-compat alias
upload_pdf = upload_document
