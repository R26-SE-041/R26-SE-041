-- Assessment tables are isolated from other BioLearnX modules.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'nishy_quiz') THEN
        EXECUTE 'CREATE SCHEMA nishy_quiz';
    END IF;
END $$;
REVOKE ALL ON SCHEMA nishy_quiz FROM PUBLIC;
SET LOCAL search_path TO nishy_quiz, pg_catalog;

CREATE TABLE IF NOT EXISTS documents (
    document_id     TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    topics          TEXT DEFAULT '[]',
    chunk_count     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'))
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL,
    created_at      TEXT DEFAULT (to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US')),
    completed_at    TEXT,
    exam_type       TEXT,
    num_questions   INTEGER,
    difficulty_mode TEXT,
    time_limit_min  INTEGER,
    status          TEXT DEFAULT 'processing',
    chroma_collection_id TEXT,
    topics_detected TEXT DEFAULT '[]',
    chunk_count     INTEGER DEFAULT 0,
    is_topic_session INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS questions (
    q_id            TEXT PRIMARY KEY,
    session_id      TEXT REFERENCES sessions(session_id),
    q_index         INTEGER,
    topic           TEXT,
    bloom_level     TEXT,
    difficulty      REAL,
    q_type          TEXT,
    question_text   TEXT,
    options_json    TEXT,
    correct_answer  TEXT,
    model_answer    TEXT,
    grounding_score REAL,
    is_flagged      INTEGER DEFAULT 0,
    source_file     TEXT DEFAULT '',
    page_number     INTEGER DEFAULT 0,
    retrieved_text  TEXT DEFAULT '',
    grounding_status TEXT DEFAULT 'rejected',
    created_at      TEXT DEFAULT (to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'))
);

CREATE TABLE IF NOT EXISTS answers (
    answer_id       TEXT PRIMARY KEY,
    session_id      TEXT REFERENCES sessions(session_id),
    q_id            TEXT REFERENCES questions(q_id),
    student_answer  TEXT,
    is_correct      INTEGER,
    score           REAL,
    attempt_number  INTEGER,
    hints_used      INTEGER DEFAULT 0,
    time_taken_sec  INTEGER,
    feedback        TEXT,
    misconception   TEXT,
    created_at      TEXT DEFAULT (to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'))
);

CREATE TABLE IF NOT EXISTS analytics (
    session_id           TEXT PRIMARY KEY REFERENCES sessions(session_id),
    final_score          REAL,
    topic_scores         TEXT,
    bloom_scores         TEXT,
    difficulty_progression TEXT,
    weak_topics          TEXT,
    strong_topics        TEXT,
    recommendations      TEXT,
    avg_grounding_score  REAL,
    flagged_count        INTEGER,
    avg_attempts         REAL,
    avg_hints_used       REAL,
    total_time_sec       INTEGER,
    created_at           TEXT DEFAULT (to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'))
);

CREATE TABLE IF NOT EXISTS research_logs (
    log_id      TEXT PRIMARY KEY,
    session_id  TEXT,
    agent_name  TEXT,
    event_type  TEXT,
    latency_ms  INTEGER,
    extra_data  TEXT,
    created_at  TEXT DEFAULT (to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'))
);

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS rating INTEGER;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS feedback_comment TEXT;
CREATE INDEX IF NOT EXISTS questions_session_idx ON questions(session_id);
CREATE INDEX IF NOT EXISTS sessions_student_idx ON sessions(student_id);
CREATE INDEX IF NOT EXISTS answers_session_idx ON answers(session_id);
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_logs ENABLE ROW LEVEL SECURITY;
-- This private schema is accessed only by the backend database role.
-- Do not add it to Supabase exposed schemas or ship DATABASE_URL to Vercel.
