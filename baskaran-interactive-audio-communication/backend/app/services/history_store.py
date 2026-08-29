"""Small, durable SQLite store for question/answer/audio history."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings


def _root() -> Path:
    path = Path(get_settings().local_history_store_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_root() / "history.sqlite3")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS history (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, question TEXT NOT NULL,
        answer TEXT NOT NULL, language TEXT NOT NULL, references_json TEXT NOT NULL,
        audio_filename TEXT, created_at TEXT NOT NULL
        )"""
    )
    return connection


def create_history(user_id: str, question: str, answer: str, language: str,
                   references: list[dict], audio: bytes | None) -> dict:
    history_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    audio_filename = None
    if audio:
        audio_filename = f"{history_id}.wav"
        (_root() / "audio").mkdir(exist_ok=True)
        (_root() / "audio" / audio_filename).write_bytes(audio)
    with _connect() as connection:
        connection.execute(
            "INSERT INTO history VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (history_id, user_id, question, answer, language,
             json.dumps(references), audio_filename, created_at),
        )
    return get_history(user_id, history_id)


def get_history(user_id: str, history_id: str) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM history WHERE id = ? AND user_id = ?", (history_id, user_id)
        ).fetchone()
    return _serialize(row) if row else None


def list_history(user_id: str) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM history WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_audio_path(user_id: str, history_id: str) -> Path | None:
    item = get_history(user_id, history_id)
    if not item or not item["has_audio"]:
        return None
    path = _root() / "audio" / f"{history_id}.wav"
    return path if path.is_file() else None


def attach_audio(user_id: str, history_id: str, audio: bytes) -> dict | None:
    if not get_history(user_id, history_id):
        return None
    filename = f"{history_id}.wav"
    (_root() / "audio").mkdir(exist_ok=True)
    (_root() / "audio" / filename).write_bytes(audio)
    with _connect() as connection:
        connection.execute(
            "UPDATE history SET audio_filename = ? WHERE id = ? AND user_id = ?",
            (filename, history_id, user_id),
        )
    return get_history(user_id, history_id)


def _serialize(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "question": row["question"], "answer": row["answer"],
        "language": row["language"], "references": json.loads(row["references_json"]),
        "has_audio": bool(row["audio_filename"]), "created_at": row["created_at"],
    }
