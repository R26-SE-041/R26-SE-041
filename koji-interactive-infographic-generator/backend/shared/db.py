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
import json
from contextlib import contextmanager
from typing import Any, Generator, Optional

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
    visual_score: Optional[float] = None,
    pedagogical_score: Optional[float] = None,
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
    if visual_score is not None:
        fields.append("visual_score = %s")
        values.append(visual_score)
    if pedagogical_score is not None:
        fields.append("pedagogical_score = %s")
        values.append(pedagogical_score)
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


def _vector_literal(values: list[float]) -> str:
    if len(values) != 384:
        raise ValueError(f"Expected a 384-dimensional embedding, got {len(values)}")
    return "[" + ",".join(f"{float(value):.8g}" for value in values) + "]"


def insert_prompt_experience(
    raw_prompt: str,
    enhanced_prompt: str,
    visual_score: float,
    pedagogical_score: float,
    prompt_embedding: list[float],
    clip_score: float | None = None,
    vlm_feedback: str | None = None,
    subject_tag: str | None = None,
    grade_tag: str | None = None,
    style_tag: str | None = None,
    skill_version: str | None = None,
) -> str:
    sql = """
        INSERT INTO prompt_experiences
            (raw_prompt, enhanced_prompt, visual_score, pedagogical_score,
             clip_score, vlm_feedback, subject_tag, grade_tag, style_tag,
             prompt_embedding, skill_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
        RETURNING id::text
    """
    values = (
        raw_prompt, enhanced_prompt, visual_score, pedagogical_score,
        clip_score, vlm_feedback, subject_tag, grade_tag, style_tag,
        _vector_literal(prompt_embedding), skill_version,
    )
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            return cur.fetchone()[0]


def insert_knowledge_chunk(
    content: str,
    source_pdf: str,
    page_num: int | None,
    subject: str | None,
    embedding: list[float],
) -> str:
    sql = """
        INSERT INTO knowledge_chunks (content, source_pdf, page_num, subject, embedding)
        VALUES (%s, %s, %s, %s, %s::vector)
        RETURNING id::text
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (content, source_pdf, page_num, subject, _vector_literal(embedding)))
            return cur.fetchone()[0]


def insert_interaction_log(
    pipeline_run_id: str | None,
    click_x: float | None,
    click_y: float | None,
    mode: str,
    user_question: str | None,
    identified_concept: str | None,
    vlm_response: str | None,
    rag_chunks_used: list[str] | None = None,
) -> str:
    sql = """
        INSERT INTO interaction_logs
            (pipeline_run_id, click_x, click_y, mode, user_question,
             identified_concept, vlm_response, rag_chunks_used)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::uuid[])
        RETURNING id::text
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                pipeline_run_id, click_x, click_y, mode, user_question,
                identified_concept, vlm_response, rag_chunks_used or [],
            ))
            return cur.fetchone()[0]


_HYBRID_TABLES = {
    "knowledge_chunks": ("content", "source_pdf"),
    "prompt_experiences": ("enhanced_prompt", "raw_prompt"),
}


def hybrid_retrieve(
    query: str,
    query_embedding: list[float],
    table: str,
    n: int = 5,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse semantic and full-text rankings using Reciprocal Rank Fusion."""
    if table not in _HYBRID_TABLES:
        raise ValueError(f"Hybrid retrieval is not allowed for table {table!r}")
    if not query.strip() or n < 1:
        return []
    content_col, source_col = _HYBRID_TABLES[table]
    candidate_limit = max(n * 4, 20)
    sql = f"""
        WITH vector_results AS (
            SELECT id, {content_col} AS content, {source_col} AS source,
                   ROW_NUMBER() OVER (ORDER BY prompt_embedding <=> %s::vector) AS vec_rank
            FROM {table}
            ORDER BY prompt_embedding <=> %s::vector
            LIMIT %s
        ),
        fts_results AS (
            SELECT id, {content_col} AS content, {source_col} AS source,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank(fts, websearch_to_tsquery('english', %s)) DESC
                   ) AS fts_rank
            FROM {table}
            WHERE fts @@ websearch_to_tsquery('english', %s)
            LIMIT %s
        ),
        combined AS (
            SELECT COALESCE(v.id, f.id) AS id,
                   COALESCE(v.content, f.content) AS content,
                   COALESCE(v.source, f.source) AS source,
                   COALESCE(1.0 / (%s + v.vec_rank), 0) +
                   COALESCE(1.0 / (%s + f.fts_rank), 0) AS rrf_score
            FROM vector_results v FULL OUTER JOIN fts_results f ON v.id = f.id
        )
        SELECT id::text, content, source, rrf_score
        FROM combined ORDER BY rrf_score DESC LIMIT %s
    """
    if table == "knowledge_chunks":
        sql = sql.replace("prompt_embedding", "embedding")
    vector = _vector_literal(query_embedding)
    params = (vector, vector, candidate_limit, query, query, candidate_limit, k, k, n)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def get_similar_experiences(raw_prompt: str, embedding: list[float], limit: int = 3) -> list[dict[str, Any]]:
    return hybrid_retrieve(raw_prompt, embedding, "prompt_experiences", limit)


def vector_retrieve(
    query_embedding: list[float],
    table: str = "knowledge_chunks",
    n: int = 5,
) -> list[dict[str, Any]]:
    if table not in _HYBRID_TABLES:
        raise ValueError(f"Vector retrieval is not allowed for table {table!r}")
    content_col, source_col = _HYBRID_TABLES[table]
    embedding_col = "embedding" if table == "knowledge_chunks" else "prompt_embedding"
    sql = f"""
        SELECT id::text, {content_col} AS content, {source_col} AS source,
               1 - ({embedding_col} <=> %s::vector) AS score
        FROM {table}
        ORDER BY {embedding_col} <=> %s::vector
        LIMIT %s
    """
    vector = _vector_literal(query_embedding)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vector, vector, n))
            return [dict(row) for row in cur.fetchall()]


def full_text_retrieve(
    query: str,
    table: str = "knowledge_chunks",
    n: int = 5,
) -> list[dict[str, Any]]:
    if table not in _HYBRID_TABLES:
        raise ValueError(f"Full-text retrieval is not allowed for table {table!r}")
    if not query.strip():
        return []
    content_col, source_col = _HYBRID_TABLES[table]
    sql = f"""
        SELECT id::text, {content_col} AS content, {source_col} AS source,
               ts_rank(fts, websearch_to_tsquery('english', %s)) AS score
        FROM {table}
        WHERE fts @@ websearch_to_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (query, query, n))
            return [dict(row) for row in cur.fetchall()]


def list_high_scoring_experiences(min_score: float = 8.0, limit: int = 200) -> list[dict[str, Any]]:
    sql = """
        SELECT id::text, raw_prompt, enhanced_prompt, visual_score,
               pedagogical_score, subject_tag, grade_tag, style_tag, skill_version
        FROM prompt_experiences
        WHERE (visual_score + pedagogical_score) / 2.0 >= %s
        ORDER BY created_at DESC LIMIT %s
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (min_score, limit))
            return [dict(row) for row in cur.fetchall()]


def consolidate_prompt_experiences(similarity_threshold: float = 0.90) -> dict[str, int]:
    """Delete lower-scoring near duplicates while retaining the best experience."""
    sql = """
        WITH ranked_duplicates AS (
            SELECT CASE
                WHEN (left_exp.visual_score + left_exp.pedagogical_score) >=
                     (right_exp.visual_score + right_exp.pedagogical_score)
                THEN right_exp.id ELSE left_exp.id
            END AS id
            FROM prompt_experiences left_exp
            JOIN prompt_experiences right_exp ON left_exp.id < right_exp.id
            WHERE 1 - (left_exp.prompt_embedding <=> right_exp.prompt_embedding) >= %s
        )
        DELETE FROM prompt_experiences
        WHERE id IN (SELECT id FROM ranked_duplicates)
        RETURNING id
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (similarity_threshold,))
            return {"deleted": len(cur.fetchall())}


def list_interaction_aggregates(days: int = 30, min_occurrences: int = 3) -> list[dict[str, Any]]:
    """Aggregate interaction behavior by normalized identified concept."""
    sql = """
        SELECT lower(trim(identified_concept)) AS concept,
               COUNT(*)::int AS occurrences,
               COUNT(*) FILTER (WHERE mode = 'identify')::int AS identify_count,
               COUNT(*) FILTER (WHERE mode = 'ask')::int AS ask_count,
               COUNT(*) FILTER (WHERE user_question IS NOT NULL AND trim(user_question) <> '')::int AS question_count,
               AVG(pr.visual_score) AS avg_visual_score,
               AVG(pr.pedagogical_score) AS avg_pedagogical_score
        FROM interaction_logs il
        LEFT JOIN pipeline_runs pr ON pr.id = il.pipeline_run_id
        WHERE il.created_at >= NOW() - (%s * INTERVAL '1 day')
          AND identified_concept IS NOT NULL
          AND trim(identified_concept) <> ''
        GROUP BY lower(trim(identified_concept))
        HAVING COUNT(*) >= %s
        ORDER BY COUNT(*) DESC
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (days, min_occurrences))
            return [dict(row) for row in cur.fetchall()]


def upsert_feedback_pattern(pattern: dict[str, Any]) -> str:
    sql = """
        INSERT INTO feedback_patterns
            (pattern_key, concept, pattern_type, occurrences, confidence,
             suggested_rule, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (pattern_key) DO UPDATE SET
            occurrences = EXCLUDED.occurrences,
            confidence = EXCLUDED.confidence,
            suggested_rule = EXCLUDED.suggested_rule,
            metadata = EXCLUDED.metadata,
            status = CASE WHEN feedback_patterns.status = 'dismissed'
                          THEN 'dismissed' ELSE 'active' END,
            last_seen_at = NOW()
        RETURNING id::text
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                pattern["pattern_key"], pattern["concept"], pattern["pattern_type"],
                pattern["occurrences"], pattern["confidence"], pattern["suggested_rule"],
                json.dumps(pattern.get("metadata") or {}),
            ))
            return cur.fetchone()[0]


def list_active_feedback_patterns(limit: int = 50) -> list[dict[str, Any]]:
    sql = """
        SELECT id::text, pattern_key, concept, pattern_type, occurrences,
               confidence, suggested_rule, metadata
        FROM feedback_patterns
        WHERE status = 'active'
        ORDER BY confidence DESC, occurrences DESC
        LIMIT %s
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            return [dict(row) for row in cur.fetchall()]


def mark_feedback_patterns_consumed(pattern_ids: list[str]) -> None:
    if not pattern_ids:
        return
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE feedback_patterns SET status = 'consumed' WHERE id = ANY(%s::uuid[])",
                (pattern_ids,),
            )


def list_validation_prompts(limit: int = 10) -> list[str]:
    """Return a deterministic held-out prompt set not selected by recency."""
    sql = """
        SELECT raw_prompt
        FROM pipeline_runs
        WHERE error IS NULL AND raw_prompt IS NOT NULL AND trim(raw_prompt) <> ''
          AND NOT EXISTS (
              SELECT 1 FROM prompt_experiences pe
              WHERE pe.raw_prompt = pipeline_runs.raw_prompt
          )
        GROUP BY raw_prompt
        ORDER BY md5(raw_prompt)
        LIMIT %s
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return [row[0] for row in cur.fetchall()]


def get_deployed_skill_version() -> dict[str, Any] | None:
    sql = """
        SELECT id::text, version, content, old_score, new_score, deployed_at
        FROM skill_versions WHERE status = 'deployed' LIMIT 1
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return dict(row) if row else None


def get_latest_skill_version_number() -> int | None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(version) FROM skill_versions")
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None


def record_skill_version(
    version: int,
    content: str,
    status: str,
    old_score: float | None,
    new_score: float | None,
    validation_count: int,
    source_experience_count: int,
    feedback_pattern_ids: list[str],
    metadata: dict[str, Any] | None = None,
) -> str:
    if status not in {"candidate", "rejected", "deployed", "superseded"}:
        raise ValueError(f"Invalid skill version status: {status}")
    with _get_conn() as conn:
        with conn.cursor() as cur:
            if status == "deployed":
                cur.execute("UPDATE skill_versions SET status = 'superseded' WHERE status = 'deployed'")
            cur.execute("""
                INSERT INTO skill_versions
                    (version, content, status, old_score, new_score, validation_count,
                     source_experience_count, feedback_pattern_ids, metadata, deployed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::uuid[], %s::jsonb,
                        CASE WHEN %s = 'deployed' THEN NOW() ELSE NULL END)
                RETURNING id::text
            """, (
                version, content, status, old_score, new_score, validation_count,
                source_experience_count, feedback_pattern_ids, json.dumps(metadata or {}), status,
            ))
            return cur.fetchone()[0]


def activate_skill_version(version: int) -> None:
    """Atomically supersede the active version and activate a committed candidate."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE skill_versions SET status = 'superseded' WHERE status = 'deployed'")
            cur.execute(
                "UPDATE skill_versions SET status = 'deployed', deployed_at = NOW() "
                "WHERE version = %s AND status = 'candidate'",
                (version,),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"Skill version {version} is not an activatable candidate")


def insert_ablation_result(result: dict[str, Any]) -> None:
    sql = """
        INSERT INTO ablation_results
            (experiment_id, config_id, prompt_id, seed, visual_score,
             pedagogical_score, clip_score, retry_count, latency_ms, error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (experiment_id, config_id, prompt_id, seed) DO UPDATE SET
            visual_score = EXCLUDED.visual_score,
            pedagogical_score = EXCLUDED.pedagogical_score,
            clip_score = EXCLUDED.clip_score,
            retry_count = EXCLUDED.retry_count,
            latency_ms = EXCLUDED.latency_ms,
            error = EXCLUDED.error
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                result["experiment_id"], result["config_id"], result["prompt_id"], result["seed"],
                result.get("visual_score"), result.get("pedagogical_score"), result.get("clip_score"),
                result.get("retry_count", 0), result.get("latency_ms"), result.get("error"),
            ))


# ── Explicit agent feedback and preference pairs ─────────────────────────────

_FEEDBACK_AGENTS = {
    "prompt-agent", "image-agent", "interactive-agent", "eval-agent", "threed-agent",
}


def record_agent_feedback(
    *,
    session_id: str,
    agent_name: str,
    output_id: str,
    rating: int,
    reason_codes: list[str],
    comment: str | None = None,
    parent_feedback_id: str | None = None,
    parent_output_id: str | None = None,
    user_id: str | None = None,
    auth_user_id: str | None = None,
    pipeline_run_id: str | None = None,
    input_context: dict[str, Any] | None = None,
    output_snapshot: dict[str, Any] | None = None,
    model_version: str | None = None,
    skill_version: str | None = None,
) -> dict[str, str | None]:
    """Persist one rating and atomically complete a preference pair when possible."""
    if agent_name not in _FEEDBACK_AGENTS:
        raise ValueError(f"Unsupported feedback agent: {agent_name}")
    if rating not in {-1, 1}:
        raise ValueError("rating must be -1 or 1")

    normalized_reasons = sorted({code.strip().lower() for code in reason_codes if code.strip()})
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO agent_feedback
                    (session_id, user_id, auth_user_id, pipeline_run_id, agent_name, output_id,
                     parent_output_id, rating, reason_codes, comment, input_context,
                     output_snapshot, model_version, skill_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::text[], %s,
                        %s::jsonb, %s::jsonb, %s, %s)
                ON CONFLICT (agent_name, output_id) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    reason_codes = EXCLUDED.reason_codes,
                    comment = EXCLUDED.comment,
                    input_context = EXCLUDED.input_context,
                    output_snapshot = EXCLUDED.output_snapshot
                RETURNING id::text
            """, (
                session_id, user_id, auth_user_id, pipeline_run_id, agent_name, output_id,
                parent_output_id, rating, normalized_reasons, comment,
                json.dumps(input_context or {}), json.dumps(output_snapshot or {}),
                model_version, skill_version,
            ))
            feedback_id = cur.fetchone()[0]
            pair_id: str | None = None
            if rating == 1 and parent_feedback_id:
                cur.execute("""
                    INSERT INTO preference_pairs
                        (agent_name, negative_feedback_id, positive_feedback_id,
                         negative_output_id, positive_output_id,
                         negative_reasons, positive_reasons)
                    SELECT n.agent_name, n.id, p.id, n.output_id, p.output_id,
                           n.reason_codes, p.reason_codes
                    FROM agent_feedback n
                    JOIN agent_feedback p ON p.id = %s::uuid
                    WHERE n.id = %s::uuid
                      AND n.rating = -1 AND p.rating = 1
                      AND n.agent_name = p.agent_name
                      AND n.session_id = p.session_id
                      AND n.auth_user_id IS NOT DISTINCT FROM p.auth_user_id
                    ON CONFLICT (negative_feedback_id) DO UPDATE SET
                        positive_feedback_id = EXCLUDED.positive_feedback_id,
                        positive_output_id = EXCLUDED.positive_output_id,
                        positive_reasons = EXCLUDED.positive_reasons
                    RETURNING id::text
                """, (feedback_id, parent_feedback_id))
                row = cur.fetchone()
                if not row:
                    raise ValueError("parent_feedback_id must reference a disliked output from the same agent and session")
                pair_id = row[0]
            return {"feedback_id": feedback_id, "preference_pair_id": pair_id}


def list_preference_reason_aggregates(
    minimum_pairs: int = 10,
    minimum_sessions: int = 3,
) -> list[dict[str, Any]]:
    """Aggregate controlled negative reason codes; comments never become instructions."""
    sql = """
        SELECT pp.agent_name, reason.reason_code,
               COUNT(DISTINCT pp.id)::int AS evidence_count,
               COUNT(DISTINCT negative.session_id)::int AS distinct_sessions,
               (ARRAY_AGG(DISTINCT pp.id::text))[1:100] AS pair_ids,
               ARRAY_AGG(DISTINCT positive.reason_code)
                   FILTER (WHERE positive.reason_code IS NOT NULL) AS positive_reasons
        FROM preference_pairs pp
        JOIN agent_feedback negative ON negative.id = pp.negative_feedback_id
        CROSS JOIN LATERAL unnest(pp.negative_reasons) AS reason(reason_code)
        LEFT JOIN LATERAL unnest(pp.positive_reasons) AS positive(reason_code) ON TRUE
        WHERE pp.status = 'active'
        GROUP BY pp.agent_name, reason.reason_code
        HAVING COUNT(DISTINCT pp.id) >= %s AND COUNT(DISTINCT negative.session_id) >= %s
        ORDER BY COUNT(DISTINCT pp.id) DESC
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (minimum_pairs, minimum_sessions))
            return [dict(row) for row in cur.fetchall()]


def upsert_memory_candidate(candidate: dict[str, Any]) -> str:
    sql = """
        INSERT INTO memory_candidates
            (fingerprint, scope, agent_name, memory_type, lesson, evidence_count,
             distinct_sessions, confidence, evidence_pair_ids, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[], %s::jsonb)
        ON CONFLICT (fingerprint) DO UPDATE SET
            lesson = EXCLUDED.lesson,
            evidence_count = EXCLUDED.evidence_count,
            distinct_sessions = EXCLUDED.distinct_sessions,
            confidence = EXCLUDED.confidence,
            evidence_pair_ids = EXCLUDED.evidence_pair_ids,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id::text
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                candidate["fingerprint"], candidate["scope"], candidate.get("agent_name"),
                candidate["memory_type"], candidate["lesson"], candidate["evidence_count"],
                candidate["distinct_sessions"], candidate["confidence"],
                candidate.get("evidence_pair_ids") or [], json.dumps(candidate.get("metadata") or {}),
            ))
            return cur.fetchone()[0]


def get_preference_pair_learning_evidence(pair_id: str) -> dict[str, Any] | None:
    sql = """
        SELECT pp.id::text, pp.agent_name, pp.negative_reasons, pp.positive_reasons,
               negative.auth_user_id::text AS auth_user_id,
               negative.input_context, negative.output_snapshot AS rejected_output,
               positive.output_snapshot AS preferred_output
        FROM preference_pairs pp
        JOIN agent_feedback negative ON negative.id = pp.negative_feedback_id
        JOIN agent_feedback positive ON positive.id = pp.positive_feedback_id
        WHERE pp.id = %s::uuid
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (pair_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def list_unembedded_preference_pair_ids(limit: int = 200) -> list[str]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id::text FROM preference_pairs
                WHERE context_embedding IS NULL AND status = 'active'
                ORDER BY created_at ASC LIMIT %s
            """, (max(1, min(limit, 1000)),))
            return [row[0] for row in cur.fetchall()]


def update_preference_pair_embedding(pair_id: str, context_text: str, embedding: list[float]) -> None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE preference_pairs SET context_text = %s, context_embedding = %s::vector WHERE id = %s::uuid",
                (context_text, _vector_literal(embedding), pair_id),
            )


def get_user_memory_settings(user_id: str) -> dict[str, Any]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT memory_enabled, updated_at FROM user_memory_settings WHERE user_id = %s::uuid",
                (user_id,),
            )
            row = cur.fetchone()
            return {
                "memory_enabled": bool(row[0]) if row else False,
                "updated_at": row[1].isoformat() if row else None,
            }


def set_user_memory_enabled(user_id: str, enabled: bool) -> dict[str, Any]:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_memory_settings (user_id, memory_enabled)
                VALUES (%s::uuid, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    memory_enabled = EXCLUDED.memory_enabled,
                    updated_at = NOW()
                RETURNING memory_enabled, updated_at
            """, (user_id, enabled))
            memory_enabled, updated_at = cur.fetchone()
            return {"memory_enabled": memory_enabled, "updated_at": updated_at.isoformat()}


def list_user_preferences(user_id: str) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id::text, agent_name, preference_key, content, confidence,
                       evidence_count, status, metadata, created_at, updated_at
                FROM user_preferences
                WHERE user_id = %s::uuid
                ORDER BY status = 'active' DESC, confidence DESC, updated_at DESC
            """, (user_id,))
            return [dict(row) for row in cur.fetchall()]


def revoke_user_preference(user_id: str, preference_id: str) -> bool:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE user_preferences SET status = 'revoked', updated_at = NOW()
                WHERE id = %s::uuid AND user_id = %s::uuid
            """, (preference_id, user_id))
            return cur.rowcount == 1


def clear_user_preferences(user_id: str) -> int:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_preferences WHERE user_id = %s::uuid", (user_id,))
            return cur.rowcount


def upsert_user_preference(
    *,
    user_id: str,
    agent_name: str,
    preference_key: str,
    content: str,
    embedding: list[float],
    preference_pair_id: str,
    metadata: dict[str, Any] | None = None,
    activation_evidence: int = 3,
) -> dict[str, Any]:
    """Add idempotent pair evidence and activate only after repeated preference."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT memory_enabled FROM user_memory_settings WHERE user_id = %s::uuid",
                (user_id,),
            )
            setting = cur.fetchone()
            if not setting or not setting[0]:
                return {
                    "preference_id": None,
                    "evidence_added": False,
                    "evidence_count": 0,
                    "confidence": 0.0,
                    "status": "disabled",
                }
            cur.execute("""
                INSERT INTO user_preferences
                    (user_id, agent_name, preference_key, content, embedding, metadata)
                VALUES (%s::uuid, %s, %s, %s, %s::vector, %s::jsonb)
                ON CONFLICT (user_id, agent_name, preference_key) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    metadata = user_preferences.metadata || EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING id::text
            """, (
                user_id, agent_name, preference_key, content,
                _vector_literal(embedding), json.dumps(metadata or {}),
            ))
            preference_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO user_preference_evidence (preference_id, preference_pair_id)
                VALUES (%s::uuid, %s::uuid)
                ON CONFLICT DO NOTHING
                RETURNING preference_id
            """, (preference_id, preference_pair_id))
            inserted = cur.fetchone() is not None
            cur.execute("""
                WITH evidence AS (
                    SELECT COUNT(*)::int AS count
                    FROM user_preference_evidence
                    WHERE preference_id = %s::uuid
                )
                UPDATE user_preferences preference
                SET evidence_count = evidence.count,
                    confidence = LEAST(0.95, 0.20 + evidence.count * 0.15),
                    status = CASE
                        WHEN preference.status = 'revoked' THEN 'revoked'
                        WHEN evidence.count >= %s THEN 'active'
                        ELSE 'candidate'
                    END,
                    updated_at = NOW()
                FROM evidence
                WHERE preference.id = %s::uuid
                RETURNING preference.evidence_count, preference.confidence, preference.status
            """, (preference_id, activation_evidence, preference_id))
            evidence_count, confidence, status = cur.fetchone()
            return {
                "preference_id": preference_id,
                "evidence_added": inserted,
                "evidence_count": evidence_count,
                "confidence": confidence,
                "status": status,
            }


def upsert_agent_memory(
    *,
    fingerprint: str,
    scope: str,
    agent_name: str | None,
    memory_type: str,
    content: str,
    embedding: list[float],
    confidence: float,
    evidence_count: int,
    source_candidate_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    sql = """
        INSERT INTO agent_memories
            (fingerprint, scope, agent_name, memory_type, content, embedding,
             confidence, evidence_count, source_candidate_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s::uuid, %s::jsonb)
        ON CONFLICT (fingerprint) DO UPDATE SET
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding,
            confidence = EXCLUDED.confidence,
            evidence_count = EXCLUDED.evidence_count,
            source_candidate_id = EXCLUDED.source_candidate_id,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id::text
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                fingerprint, scope, agent_name, memory_type, content,
                _vector_literal(embedding), confidence, evidence_count,
                source_candidate_id, json.dumps(metadata or {}),
            ))
            return cur.fetchone()[0]


def list_agent_memories(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    sql = """
        SELECT id::text, fingerprint, scope, agent_name, memory_type, content,
               confidence, evidence_count, status, source_candidate_id::text,
               metadata, created_at, updated_at, deployed_at
        FROM agent_memories
        WHERE (%s IS NULL OR status = %s)
        ORDER BY confidence DESC, evidence_count DESC, updated_at DESC
        LIMIT %s
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (status, status, max(1, min(limit, 500))))
            return [dict(row) for row in cur.fetchall()]


def transition_agent_memory(memory_id: str, target_status: str) -> dict[str, Any]:
    transitions = {
        "approved": {"proposed"},
        "rejected": {"proposed", "approved"},
        "deployed": {"approved"},
        "superseded": {"deployed"},
    }
    if target_status not in transitions:
        raise ValueError(f"Unsupported target status: {target_status}")
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                UPDATE agent_memories
                SET status = %s,
                    deployed_at = CASE WHEN %s = 'deployed' THEN NOW() ELSE deployed_at END,
                    updated_at = NOW()
                WHERE id = %s::uuid AND status = ANY(%s::text[])
                RETURNING id::text, scope, agent_name, memory_type, content, status,
                          confidence, evidence_count, deployed_at, source_candidate_id::text
            """, (target_status, target_status, memory_id, list(transitions[target_status])))
            row = cur.fetchone()
            if not row:
                raise ValueError("Memory does not exist or status transition is not allowed")
            result = dict(row)
            source_candidate_id = result.pop("source_candidate_id", None)
            if source_candidate_id and target_status in {"approved", "rejected", "deployed"}:
                cur.execute("""
                    UPDATE memory_candidates
                    SET status = %s,
                        deployed_at = CASE WHEN %s = 'deployed' THEN NOW() ELSE deployed_at END,
                        updated_at = NOW()
                    WHERE id = %s::uuid
                """, (target_status, target_status, source_candidate_id))
            return result


def retrieve_scoped_memories(
    *,
    query_embedding: list[float],
    agent_name: str,
    user_id: str | None = None,
    limit: int = 5,
    minimum_similarity: float = 0.25,
) -> list[dict[str, Any]]:
    """Retrieve deployed global/agent memory plus only the authenticated user's preferences."""
    vector = _vector_literal(query_embedding)
    sql = """
        WITH candidates AS (
            SELECT id::text, content, 'agent_memory'::text AS source,
                   scope, confidence, evidence_count,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM agent_memories
            WHERE status = 'deployed'
              AND (scope = 'global' OR (scope = 'agent' AND agent_name = %s))
            UNION ALL
            SELECT id::text, content, 'user_preference'::text AS source,
                   'user'::text AS scope, confidence, evidence_count,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM user_preferences
            WHERE %s::uuid IS NOT NULL
              AND user_id = %s::uuid
              AND agent_name = %s
              AND status = 'active'
              AND EXISTS (
                  SELECT 1 FROM user_memory_settings setting
                  WHERE setting.user_id = user_preferences.user_id
                    AND setting.memory_enabled = TRUE
              )
        )
        SELECT id, content, source, scope, confidence, evidence_count, similarity,
               similarity * 0.65 + confidence * 0.25 +
               LEAST(evidence_count / 10.0, 1.0) * 0.10 AS score
        FROM candidates
        WHERE similarity >= %s
        ORDER BY score DESC
        LIMIT %s
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (
                vector, agent_name, vector, user_id, user_id, agent_name,
                minimum_similarity, max(1, min(limit, 10)),
            ))
            return [dict(row) for row in cur.fetchall()]
