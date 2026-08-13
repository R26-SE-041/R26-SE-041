"""
shared/db.py
────────────
Supabase (PostgreSQL) helpers for persisting pipeline runs.

DESIGN DECISIONS:
  - Connection is opened per-call inside a context manager.
    Never at module level — Modal containers are ephemeral and a
    module-level connection will time out or leak between invocations.
  - DATABASE_URL is read from the environment (Modal secret: supabase-secret).
  - Image bytes stored as BYTEA in Supabase. If you later prefer Supabase
    Storage + signed URLs, swap out insert_pipeline_record and
    update_image here only.

SUPABASE TABLE — run this migration once in the Supabase SQL editor:

    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        raw_prompt       TEXT NOT NULL,
        enhanced_prompt  TEXT,
        image_data       BYTEA,
        clip_score       DOUBLE PRECISION,
        vlm_score        DOUBLE PRECISION,
        vlm_feedback     TEXT,
        prompt_parse_err BOOLEAN DEFAULT FALSE,
        error            TEXT,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
import psycopg2.extras  # for DictCursor


# ── Connection ────────────────────────────────────────────────────────────────

@contextmanager
def _get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Yield a psycopg2 connection.
    Commits on clean exit, rolls back on exception, always closes.
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Write operations ──────────────────────────────────────────────────────────

def insert_pipeline_record(
    raw_prompt: str,
    enhanced_prompt: Optional[str] = None,
    prompt_parse_err: bool = False,
    error: Optional[str] = None,
) -> str:
    """
    Insert a new pipeline run row and return its UUID.
    Called at the start of the db node (before image/eval data is available).
    Follow up with update_pipeline_record() once image + eval are ready.
    """
    sql = """
        INSERT INTO pipeline_runs
            (raw_prompt, enhanced_prompt, prompt_parse_err, error)
        VALUES (%s, %s, %s, %s)
        RETURNING id::text
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (raw_prompt, enhanced_prompt, prompt_parse_err, error))
            row = cur.fetchone()
            return row[0]


def update_pipeline_record(
    record_id: str,
    image_data: Optional[bytes] = None,
    clip_score: Optional[float] = None,
    vlm_score: Optional[float] = None,
    vlm_feedback: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """
    Update an existing pipeline run with image + evaluation results.
    Only non-None kwargs are written — avoids overwriting partial data.
    """
    fields: list[str] = []
    values: list = []

    if image_data is not None:
        fields.append("image_data = %s")
        values.append(psycopg2.Binary(image_data))
    if clip_score is not None:
        fields.append("clip_score = %s")
        values.append(clip_score)
    if vlm_score is not None:
        fields.append("vlm_score = %s")
        values.append(vlm_score)
    if vlm_feedback is not None:
        fields.append("vlm_feedback = %s")
        values.append(vlm_feedback)
    if error is not None:
        fields.append("error = %s")
        values.append(error)

    if not fields:
        return  # nothing to update

    sql = f"UPDATE pipeline_runs SET {', '.join(fields)} WHERE id = %s"
    values.append(record_id)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, values)
