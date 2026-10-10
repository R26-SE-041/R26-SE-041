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

-- Explicit user feedback is immutable evidence. Markdown memories are derived,
-- versioned deployment artifacts and are never used as the source of truth.
CREATE TABLE IF NOT EXISTS agent_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL CHECK (char_length(session_id) BETWEEN 1 AND 128),
    user_id TEXT,
    auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    agent_name TEXT NOT NULL CHECK (agent_name IN (
        'prompt-agent', 'image-agent', 'interactive-agent', 'eval-agent', 'threed-agent'
    )),
    output_id TEXT NOT NULL CHECK (char_length(output_id) BETWEEN 1 AND 128),
    parent_output_id TEXT,
    rating SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    reason_codes TEXT[] NOT NULL DEFAULT '{}',
    comment TEXT CHECK (comment IS NULL OR char_length(comment) <= 2000),
    input_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT,
    skill_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_name, output_id)
);

ALTER TABLE agent_feedback
    ADD COLUMN IF NOT EXISTS auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_agent_feedback_learning
    ON agent_feedback(agent_name, rating, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_session
    ON agent_feedback(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_auth_user
    ON agent_feedback(auth_user_id, agent_name, created_at DESC)
    WHERE auth_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS preference_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    negative_feedback_id UUID NOT NULL UNIQUE REFERENCES agent_feedback(id) ON DELETE CASCADE,
    positive_feedback_id UUID NOT NULL UNIQUE REFERENCES agent_feedback(id) ON DELETE CASCADE,
    negative_output_id TEXT NOT NULL,
    positive_output_id TEXT NOT NULL,
    negative_reasons TEXT[] NOT NULL DEFAULT '{}',
    positive_reasons TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'consumed', 'dismissed')),
    context_text TEXT,
    context_embedding VECTOR(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (negative_output_id <> positive_output_id)
);

ALTER TABLE preference_pairs ADD COLUMN IF NOT EXISTS context_text TEXT;
ALTER TABLE preference_pairs ADD COLUMN IF NOT EXISTS context_embedding VECTOR(384);

CREATE INDEX IF NOT EXISTS idx_preference_pairs_agent
    ON preference_pairs(agent_name, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_preference_pairs_embedding
    ON preference_pairs USING hnsw (context_embedding vector_cosine_ops)
    WHERE context_embedding IS NOT NULL;

CREATE TABLE IF NOT EXISTS memory_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'agent')),
    agent_name TEXT CHECK (
        (scope = 'global' AND agent_name IS NULL) OR
        (scope = 'agent' AND agent_name IN (
            'prompt-agent', 'image-agent', 'interactive-agent', 'eval-agent', 'threed-agent'
        ))
    ),
    memory_type TEXT NOT NULL CHECK (memory_type IN ('memento', 'skill')),
    lesson TEXT NOT NULL,
    evidence_count INTEGER NOT NULL CHECK (evidence_count > 0),
    distinct_sessions INTEGER NOT NULL CHECK (distinct_sessions > 0),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence_pair_ids UUID[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (
        status IN ('proposed', 'approved', 'rejected', 'deployed')
    ),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deployed_at TIMESTAMPTZ
);

-- Distinct authors behind the evidence, not distinct sessions — one user
-- opening several sessions must not be able to satisfy a "many users" bar alone.
ALTER TABLE memory_candidates ADD COLUMN IF NOT EXISTS distinct_users INTEGER NOT NULL DEFAULT 1 CHECK (distinct_users > 0);

CREATE INDEX IF NOT EXISTS idx_memory_candidates_review
    ON memory_candidates(status, memory_type, confidence DESC);

-- Runtime memories use pgvector retrieval. Candidate evidence remains separate
-- so unreviewed feedback can never silently enter an agent prompt.
CREATE TABLE IF NOT EXISTS agent_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'agent')),
    agent_name TEXT CHECK (
        (scope = 'global' AND agent_name IS NULL) OR
        (scope = 'agent' AND agent_name IN (
            'prompt-agent', 'image-agent', 'interactive-agent', 'eval-agent', 'threed-agent'
        ))
    ),
    memory_type TEXT NOT NULL CHECK (memory_type IN ('memento', 'skill')),
    content TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence_count INTEGER NOT NULL CHECK (evidence_count > 0),
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (
        status IN ('proposed', 'approved', 'rejected', 'deployed', 'superseded')
    ),
    source_candidate_id UUID REFERENCES memory_candidates(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deployed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_memories_embedding
    ON agent_memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_agent_memories_scope
    ON agent_memories(status, scope, agent_name, confidence DESC);

CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL CHECK (agent_name IN (
        'prompt-agent', 'image-agent', 'interactive-agent', 'eval-agent', 'threed-agent'
    )),
    preference_key TEXT NOT NULL CHECK (char_length(preference_key) BETWEEN 1 AND 100),
    content TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.35 CHECK (confidence BETWEEN 0 AND 1),
    evidence_count INTEGER NOT NULL DEFAULT 1 CHECK (evidence_count > 0),
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'active', 'revoked')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, agent_name, preference_key)
);

CREATE TABLE IF NOT EXISTS user_memory_settings (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    memory_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_embedding
    ON user_preferences USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_user_preferences_lookup
    ON user_preferences(user_id, agent_name, status, confidence DESC);

CREATE TABLE IF NOT EXISTS user_preference_evidence (
    preference_id UUID NOT NULL REFERENCES user_preferences(id) ON DELETE CASCADE,
    preference_pair_id UUID NOT NULL REFERENCES preference_pairs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (preference_id, preference_pair_id)
);

-- Supabase API access is user-scoped. The server-side DATABASE_URL connection
-- performs trusted consolidation and never exposes service credentials.
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preference_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_memory_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE preference_pairs ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_candidates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own preferences" ON user_preferences;
CREATE POLICY "Users manage own preferences" ON user_preferences
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users read own feedback" ON agent_feedback;
CREATE POLICY "Users read own feedback" ON agent_feedback
    FOR SELECT USING (auth.uid() = auth_user_id);

DROP POLICY IF EXISTS "Users read own preference pairs" ON preference_pairs;
CREATE POLICY "Users read own preference pairs" ON preference_pairs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM agent_feedback feedback
            WHERE feedback.id = negative_feedback_id
              AND feedback.auth_user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users manage own memory settings" ON user_memory_settings;
CREATE POLICY "Users manage own memory settings" ON user_memory_settings
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users read own preference evidence" ON user_preference_evidence;
CREATE POLICY "Users read own preference evidence" ON user_preference_evidence
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_preferences preference
            WHERE preference.id = preference_id AND preference.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Deployed agent memories are readable" ON agent_memories;
CREATE POLICY "Deployed agent memories are readable" ON agent_memories
    FOR SELECT USING (status = 'deployed');
