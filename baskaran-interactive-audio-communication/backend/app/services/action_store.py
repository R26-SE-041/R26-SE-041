"""Persistent action tickets and summary artifacts, independent of Q&A storage."""

import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings


def root() -> Path:
    path = Path(get_settings().actions_store_path)
    return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path


@contextmanager
def connection():
    root().mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root() / "actions.sqlite3", timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, session_id TEXT NOT NULL,
        document_id TEXT NOT NULL, intent TEXT NOT NULL, expires REAL NOT NULL,
        data TEXT NOT NULL)""")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create(user_id, session_id, document_id, intent, previous=None, language="english", revision_mode="single"):
    ticket = secrets.token_urlsafe(32)
    data = {"status": "queued", "summary": None, "summary_id": None,
            "filename": None, "saved": False, "error": None, "trace": [],
            "audio_id": None, "audio_saved": False, "audio_duration": None,
            "language": language, "summary_language": "english",
            "revision_mode": revision_mode, "sections": [], "source_hash": None, "manifest_id": None,
            "timeout_seconds": (getattr(get_settings(), "actions_sectioned_timeout_seconds", 1800)
                                if intent == "audio_revision" and revision_mode == "sectioned"
                                else get_settings().actions_timeout_seconds)}
    if previous:
        data.update({key: previous[key] for key in ("summary", "summary_id", "filename")})
        data["summary_language"] = previous.get("summary_language", "english")
    with connection() as db:
        db.execute("INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (ticket, user_id, session_id, document_id, intent,
                    time.time() + data["timeout_seconds"] + 60, json.dumps(data)))
    return ticket


def get(ticket, user_id=None):
    with connection() as db:
        row = db.execute("SELECT * FROM actions WHERE id=?", (ticket,)).fetchone()
    if row is None or (user_id is not None and row["user_id"] != user_id):
        raise ValueError("Action not found.")
    return {**dict(row), **json.loads(row["data"])}


def update(ticket, **fields):
    with connection() as db:
        row = db.execute("SELECT data FROM actions WHERE id=?", (ticket,)).fetchone()
        data = json.loads(row["data"])
        data.update(fields)
        db.execute("UPDATE actions SET data=? WHERE id=?", (json.dumps(data), ticket))


def latest(user_id, session_id, document_id, language="english"):
    with connection() as db:
        rows = db.execute("""SELECT id FROM actions WHERE user_id=? AND session_id=?
            AND document_id=? ORDER BY rowid DESC""", (user_id, session_id, document_id)).fetchall()
    for row in rows:
        action = get(row["id"], user_id)
        if (action["summary"] and action.get("language", "english") == language
                and action.get("summary_language", "english") == language):
            return action
    return None


def artifact(summary_id, extension="txt"):
    # Only server-generated hex IDs are valid filenames.
    if len(summary_id) != 32 or any(c not in "0123456789abcdef" for c in summary_id):
        raise ValueError("Invalid summary ID.")
    if extension not in {"txt", "wav", "json"}:
        raise ValueError("Invalid artifact format.")
    path = root() / "files" / f"{summary_id}.{extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
