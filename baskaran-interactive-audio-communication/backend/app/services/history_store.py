"""Small, durable SQLite store for question/answer/audio history."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.services import cloud_user_store as cloud


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
                   references: list[dict], audio: bytes | None, question_audio: bytes | None = None,
                   document_grounded: bool = True, source_id: str | None = None,
                   created_at: str | None = None) -> dict:
    if cloud.enabled():
        cloud.owner_path(user_id, 'validate-owner')
        if source_id:
            rows = cloud.request('GET', '/rest/v1/study_history', params={'user_id': 'eq.' + user_id, 'source_id': 'eq.' + source_id})
            if rows:
                return rows[0]
        record = {'id': str(uuid.uuid4()), 'user_id': user_id, 'question': question,
                  'answer': answer, 'language': language, 'references': references,
                  'document_grounded': document_grounded, 'source_id': source_id,
                  'created_at': created_at or datetime.now(timezone.utc).isoformat(),
                  'has_audio': bool(audio), 'has_question_audio': bool(question_audio)}
        for kind, content in [('answer', audio), ('question', question_audio)]:
            if content:
                cloud.upload('study-history', cloud.owner_path(user_id, record['id'] + '-' + kind + '.audio'), content, 'application/octet-stream')
        rows = cloud.request('POST', '/rest/v1/study_history', json=record,
                             params={'on_conflict': 'user_id,source_id'} if source_id else None,
                             headers={'Prefer': 'resolution=ignore-duplicates,return=representation'} if source_id else None)
        if rows:
            return rows[0]
        # Another device may have imported the same legacy entry concurrently.
        cloud.remove('study-history', [cloud.owner_path(user_id, record['id'] + '-' + kind + '.audio')
                                      for kind in ('answer', 'question')])
        return cloud.request('GET', '/rest/v1/study_history', params={'user_id': 'eq.' + user_id, 'source_id': 'eq.' + source_id})[0]
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
    if cloud.enabled():
        rows = cloud.request('GET', '/rest/v1/study_history', params={'id': 'eq.' + history_id, 'user_id': 'eq.' + user_id})
        return rows[0] if rows else None
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM history WHERE id = ? AND user_id = ?", (history_id, user_id)
        ).fetchone()
    return _serialize(row) if row else None


def list_history(user_id: str) -> list[dict]:
    if cloud.enabled():
        return cloud.request('GET', '/rest/v1/study_history', params={'user_id': 'eq.' + user_id, 'order': 'created_at.desc', 'select': '*'})
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM history WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_audio_path(user_id: str, history_id: str, kind: str = 'answer') -> Path | None:
    item = get_history(user_id, history_id)
    if not item or not item.get('has_question_audio' if kind == 'question' else 'has_audio'):
        return None
    if cloud.enabled():
        filename = str(uuid.UUID(history_id)) + '-' + kind + '.audio'
        key = cloud.owner_path(user_id, filename)
        path = _root() / 'cache' / str(uuid.UUID(user_id)) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        # Re-fetch on playback so another device's edits never use stale audio.
        path.write_bytes(cloud.download('study-history', key))
        return path
    path = _root() / "audio" / f"{history_id}.wav"
    return path if path.is_file() else None


def attach_audio(user_id: str, history_id: str, audio: bytes) -> dict | None:
    if not get_history(user_id, history_id):
        return None
    if cloud.enabled():
        filename = str(uuid.UUID(history_id)) + '-answer.audio'
        cloud.upload('study-history', cloud.owner_path(user_id, filename), audio, 'application/octet-stream')
        return cloud.request('PATCH', '/rest/v1/study_history', params={'id': 'eq.' + history_id, 'user_id': 'eq.' + user_id}, json={'has_audio': True})[0]
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


def update_answer(user_id, history_id, answer):
    if cloud.enabled():
        rows = cloud.request('PATCH', '/rest/v1/study_history', params={'id': 'eq.' + history_id, 'user_id': 'eq.' + user_id}, json={'answer': answer, 'has_audio': False})
        return rows[0] if rows else None
    with _connect() as db:
        db.execute('UPDATE history SET answer=?,audio_filename=NULL WHERE id=? AND user_id=?', (answer, history_id, user_id))
    return get_history(user_id, history_id)


def delete_history(user_id, history_id=None):
    if cloud.enabled():
        params = {'user_id': 'eq.' + user_id}
        if history_id:
            params['id'] = 'eq.' + history_id
        rows = cloud.request('GET', '/rest/v1/study_history', params=params)
        if history_id and not rows:
            return False
        paths = [cloud.owner_path(user_id, str(uuid.UUID(row['id'])) + '-' + kind + '.audio')
                 for row in rows for kind in ('answer', 'question')]
        cloud.remove('study-history', paths)
        cloud.request('DELETE', '/rest/v1/study_history', params=params)
        for row in rows:
            for kind in ('answer', 'question'):
                path = _root() / 'cache' / str(uuid.UUID(user_id)) / (str(uuid.UUID(row['id'])) + '-' + kind + '.audio')
                path.unlink(missing_ok=True)
        return True
    with _connect() as db:
        if history_id:
            db.execute('DELETE FROM history WHERE id=? AND user_id=?', (history_id, user_id))
        else:
            db.execute('DELETE FROM history WHERE user_id=?', (user_id,))
    return True
