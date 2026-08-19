"""Filesystem-backed temporary document storage used while Supabase is unavailable."""

import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings


def _root() -> Path:
    """Return the configured store directory, relative to the backend root by default."""
    configured = Path(get_settings().local_document_store_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[2] / configured


def _connection() -> sqlite3.Connection:
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(root / "documents.sqlite3", timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            chunk_count INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            file_path TEXT NOT NULL
        )"""
    )
    return connection


def save_document(*, document_id: str, user_id: str, filename: str, file_type: str,
                  chunk_count: int, uploaded_at: datetime, content: bytes) -> str:
    """Persist one original file and its list-display metadata under its UUID."""
    root = _root()
    file_path = root / "files" / f"{document_id}{Path(filename).suffix.lower()}"
    storage_path = f"local/{document_id}/{filename}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    with _connection() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO documents
               (document_id, user_id, filename, file_type, chunk_count, uploaded_at, storage_path, file_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (document_id, user_id, filename, file_type, chunk_count, uploaded_at.isoformat(),
             storage_path, str(file_path.relative_to(root))),
        )
    return storage_path


def list_documents(user_id: str) -> list[dict]:
    """Return persisted documents for one user, newest first."""
    with _connection() as connection:
        rows = connection.execute(
            "SELECT * FROM documents WHERE user_id = ? ORDER BY uploaded_at DESC", (user_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def list_all_documents() -> list[dict]:
    """Return every locally persisted document for embedding migrations."""
    with _connection() as connection:
        rows = connection.execute("SELECT * FROM documents ORDER BY uploaded_at ASC").fetchall()
    return [dict(row) for row in rows]


def read_document(record: dict) -> bytes:
    """Read an original local upload using its generated, safe filename."""
    file_path = _root() / "files" / Path(record["file_path"]).name
    return file_path.read_bytes()


def get_document(document_id: str, user_id: str) -> dict | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE document_id = ? AND user_id = ?", (document_id, user_id)
        ).fetchone()
    return dict(row) if row else None


def delete_document(document_id: str, user_id: str) -> bool:
    """Remove exactly one locally stored original file and its metadata record."""
    with _connection() as connection:
        row = connection.execute(
            "SELECT file_path FROM documents WHERE document_id = ? AND user_id = ?", (document_id, user_id)
        ).fetchone()
        if not row:
            return False
        # Use only a generated filename; never trust database path components.
        file_path = _root() / "files" / Path(row["file_path"]).name
        if file_path.exists():
            file_path.unlink()
        connection.execute(
            "DELETE FROM documents WHERE document_id = ? AND user_id = ?", (document_id, user_id)
        )
    return True
