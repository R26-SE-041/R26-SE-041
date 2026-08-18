CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_prompt TEXT NOT NULL,
    enhanced_prompt TEXT,
    image_data BYTEA,
    clip_score DOUBLE PRECISION,
    vlm_score DOUBLE PRECISION,
    visual_score DOUBLE PRECISION,
    pedagogical_score DOUBLE PRECISION,
    vlm_feedback TEXT,
    prompt_parse_err BOOLEAN DEFAULT FALSE,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS visual_score DOUBLE PRECISION;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS pedagogical_score DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    source_pdf TEXT NOT NULL,
    page_num INTEGER,
    subject TEXT,
    embedding VECTOR(384) NOT NULL,
    fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON knowledge_chunks USING gin(fts);

CREATE TABLE IF NOT EXISTS prompt_experiences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_prompt TEXT NOT NULL,
    enhanced_prompt TEXT NOT NULL,
    visual_score DOUBLE PRECISION NOT NULL CHECK (visual_score BETWEEN 0 AND 10),
    pedagogical_score DOUBLE PRECISION NOT NULL CHECK (pedagogical_score BETWEEN 0 AND 10),
    clip_score DOUBLE PRECISION,
    vlm_feedback TEXT,
    subject_tag TEXT,
    grade_tag TEXT,
    style_tag TEXT,
    skill_version TEXT,
    prompt_embedding VECTOR(384) NOT NULL,
    fts TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', raw_prompt || ' ' || enhanced_prompt)
    ) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exp_embedding ON prompt_experiences
    USING hnsw (prompt_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_exp_fts ON prompt_experiences USING gin(fts);

CREATE TABLE IF NOT EXISTS interaction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    click_x DOUBLE PRECISION,
    click_y DOUBLE PRECISION,
    mode TEXT NOT NULL,
    user_question TEXT,
    identified_concept TEXT,
    vlm_response TEXT,
    rag_chunks_used UUID[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id UUID NOT NULL,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    agent TEXT NOT NULL,
    event TEXT NOT NULL,
    latency_ms DOUBLE PRECISION,
    token_count INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_traces_trace_id ON agent_traces(trace_id);

CREATE TABLE IF NOT EXISTS feedback_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_key TEXT NOT NULL UNIQUE,
    concept TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    occurrences INTEGER NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    suggested_rule TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'consumed', 'dismissed')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_patterns_status
    ON feedback_patterns(status, confidence DESC);

CREATE TABLE IF NOT EXISTS skill_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version INTEGER NOT NULL UNIQUE,
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'rejected', 'deployed', 'superseded')),
    old_score DOUBLE PRECISION,
    new_score DOUBLE PRECISION,
    validation_count INTEGER NOT NULL DEFAULT 0,
    source_experience_count INTEGER NOT NULL DEFAULT 0,
    feedback_pattern_ids UUID[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deployed_at TIMESTAMPTZ
);

ALTER TABLE skill_versions DROP CONSTRAINT IF EXISTS skill_versions_status_check;
ALTER TABLE skill_versions ADD CONSTRAINT skill_versions_status_check
    CHECK (status IN ('candidate', 'rejected', 'deployed', 'superseded'));

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_deployed_skill
    ON skill_versions(status) WHERE status = 'deployed';

CREATE TABLE IF NOT EXISTS ablation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL,
    config_id TEXT NOT NULL,
    prompt_id TEXT NOT NULL,
    seed INTEGER NOT NULL,
    visual_score DOUBLE PRECISION,
    pedagogical_score DOUBLE PRECISION,
    clip_score DOUBLE PRECISION,
    retry_count INTEGER NOT NULL DEFAULT 0,
    latency_ms DOUBLE PRECISION,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id, config_id, prompt_id, seed)
);

CREATE INDEX IF NOT EXISTS idx_ablation_results_experiment
    ON ablation_results(experiment_id, config_id);
