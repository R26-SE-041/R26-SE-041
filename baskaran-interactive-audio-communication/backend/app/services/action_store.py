"""Persistent action tickets and summary artifacts, independent of Q&A storage."""

import json
import secrets
import sqlite3
import time
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings
from app.services import cloud_user_store as cloud


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
            "created_at": datetime.now(timezone.utc).isoformat(),
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
    if cloud.enabled():
        cloud.owner_path(user_id, 'validate-owner')
        cloud.request('POST', '/rest/v1/saved_actions', json={
            'id': ticket, 'user_id': user_id, 'session_id': session_id,
            'document_id': document_id, 'intent': intent,
            'expires': time.time() + data['timeout_seconds'] + 60, 'data': data})
        return ticket
    with connection() as db:
        db.execute("INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (ticket, user_id, session_id, document_id, intent,
                    time.time() + data["timeout_seconds"] + 60, json.dumps(data)))
    return ticket


def get(ticket, user_id=None):
    if cloud.enabled():
        params = {'id': 'eq.' + ticket, 'select': '*'}
        if user_id is not None:
            params['user_id'] = 'eq.' + user_id
        rows = cloud.request('GET', '/rest/v1/saved_actions', params=params)
        if not rows:
            raise ValueError('Action not found.')
        action = {**rows[0], **rows[0]['data']}
        if action.get('saved'):
            restore_artifacts(action)
        return action
    with connection() as db:
        row = db.execute("SELECT * FROM actions WHERE id=?", (ticket,)).fetchone()
    if row is None or (user_id is not None and row["user_id"] != user_id):
        raise ValueError("Action not found.")
    return {**dict(row), **json.loads(row["data"])}


def update(ticket, **fields):
    if cloud.enabled():
        if fields.get('saved'):
            action = get(ticket)
            publish_artifacts({**action, **fields})
        rows = cloud.request('POST', '/rest/v1/rpc/patch_saved_action', json={'ticket': ticket, 'patch': fields})
        if not rows:
            raise ValueError('Action not found.')
        return
    with connection() as db:
        row = db.execute("SELECT data FROM actions WHERE id=?", (ticket,)).fetchone()
        data = json.loads(row["data"])
        data.update(fields)
        db.execute("UPDATE actions SET data=? WHERE id=?", (json.dumps(data), ticket))


def latest(user_id, session_id, document_id, language="english"):
    if cloud.enabled():
        rows = cloud.request('GET', '/rest/v1/saved_actions', params={
            'user_id': 'eq.' + user_id, 'session_id': 'eq.' + session_id,
            'document_id': 'eq.' + document_id, 'select': '*', 'order': 'created_at.desc'})
        for row in rows:
            action = {**row, **row['data']}
            if (action['intent'] != 'flashcards' and action.get('summary')
                    and action.get('language', 'english') == language
                    and action.get('summary_language', 'english') == language):
                if action.get('saved'):
                    restore_artifacts(action)
                return action
        return None
    with connection() as db:
        rows = db.execute("""SELECT id FROM actions WHERE user_id=? AND session_id=?
            AND document_id=? ORDER BY rowid DESC""", (user_id, session_id, document_id)).fetchall()
    for row in rows:
        action = get(row["id"], user_id)
        if (action["intent"] != "flashcards" and action["summary"] and action.get("language", "english") == language
                and action.get("summary_language", "english") == language):
            return action
    return None


def saved_actions(user_id):
    if cloud.enabled():
        rows = cloud.request('GET', '/rest/v1/saved_actions', params={
            'user_id': 'eq.' + user_id, 'saved': 'eq.true', 'select': '*', 'order': 'created_at.desc'})
        return [{**row, **row['data']} for row in rows]
    with connection() as db:
        rows = db.execute("SELECT * FROM actions WHERE user_id=? ORDER BY rowid DESC", (user_id,)).fetchall()
    return [{**dict(row), **json.loads(row["data"])} for row in rows
            if json.loads(row["data"]).get("saved")]


def _artifacts(data):
    refs = set()
    for key, ext in (("summary_id", "txt"), ("audio_id", "wav"), ("manifest_id", "json"), ("flashcards_id", "json")):
        if data.get(key):
            refs.add((data[key], ext))
    for section in data.get("sections", []):
        if section.get("audio_id"):
            refs.add((section["audio_id"], "wav"))
    return refs


def delete_saved(ticket, user_id):
    """Delete only this owned, closed record and artifacts no other ticket references."""
    if cloud.enabled():
        action = get(ticket, user_id)
        if not action.get('saved') or action['status'] not in {'complete', 'partial', 'failed'}:
            raise ValueError('Only a finished saved revision or deck can be deleted.')
        others = cloud.request('GET', '/rest/v1/saved_actions', params={
            'user_id': 'eq.' + user_id, 'id': 'neq.' + ticket, 'select': 'data'})
        remaining = set()
        for other in others:
            remaining.update(_artifacts(other['data']))
        removable = _artifacts(action) - remaining
        cloud.remove('revisions', [cloud.owner_path(user_id, f'{identifier}.{ext}') for identifier, ext in removable])
        cloud.request('DELETE', '/rest/v1/saved_actions', params={'id': 'eq.' + ticket, 'user_id': 'eq.' + user_id})
        for identifier, ext in removable:
            artifact(identifier, ext).unlink(missing_ok=True)
        return
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM actions WHERE id=? AND user_id=?", (ticket, user_id)).fetchone()
        if row is None:
            raise ValueError("Action not found.")
        data = json.loads(row["data"])
        if not data.get("saved") or data["status"] not in {"complete", "partial", "failed"}:
            raise ValueError("Only a finished saved revision or deck can be deleted.")
        db.execute("DELETE FROM actions WHERE id=? AND user_id=?", (ticket, user_id))
        remaining = set()
        for other in db.execute("SELECT data FROM actions"):
            remaining.update(_artifacts(json.loads(other["data"])))
        # Only validated server IDs under files/ can be removed; never recurse.
        for identifier, ext in _artifacts(data) - remaining:
            artifact(identifier, ext).unlink(missing_ok=True)


def artifact(summary_id, extension="txt"):
    # Only server-generated hex IDs are valid filenames.
    if len(summary_id) != 32 or any(c not in "0123456789abcdef" for c in summary_id):
        raise ValueError("Invalid summary ID.")
    if extension not in {"txt", "wav", "json"}:
        raise ValueError("Invalid artifact format.")
    path = root() / "files" / f"{summary_id}.{extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def publish_artifacts(action):
    """A saved flag is committed only after every referenced object is uploaded."""
    for identifier, extension in _artifacts(action):
        path = artifact(identifier, extension)
        mime = {'txt': 'text/plain', 'json': 'application/json', 'wav': 'audio/wav'}[extension]
        cloud.upload('revisions', cloud.owner_path(action['user_id'], path.name), path.read_bytes(), mime)


def restore_artifacts(action):
    """Local files are disposable playback/generation cache, not the saved library."""
    for identifier, extension in _artifacts(action):
        path = artifact(identifier, extension)
        if not path.is_file():
            content = cloud.download('revisions', cloud.owner_path(action['user_id'], path.name))
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as file:
                temporary = Path(file.name)
                file.write(content)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
