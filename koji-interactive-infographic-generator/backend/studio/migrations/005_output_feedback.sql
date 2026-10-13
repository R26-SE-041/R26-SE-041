begin;
set local search_path=public,extensions;
-- Existing feedback service contracts, provisioned with the Studio workspace.
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

CREATE TABLE IF NOT EXISTS agent_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL CHECK (char_length(session_id) BETWEEN 1 AND 128),
    user_id TEXT,
    auth_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    agent_name TEXT NOT NULL CHECK (agent_name IN (
        'prompt-agent', 'prompt-anatomy', 'prompt-generic', 'image-agent', 'interactive-agent', 'eval-agent', 'threed-agent'
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


alter table public.pipeline_runs enable row level security;
alter table public.agent_feedback enable row level security;
alter table public.preference_pairs enable row level security;
revoke all on public.pipeline_runs,public.agent_feedback,public.preference_pairs from anon,authenticated;
grant select on public.agent_feedback,public.preference_pairs to authenticated;
drop policy if exists "Users read own feedback" on public.agent_feedback;
create policy "Users read own feedback" on public.agent_feedback for select to authenticated
    using((select auth.uid())=auth_user_id);
drop policy if exists "Users read own preference pairs" on public.preference_pairs;
create policy "Users read own preference pairs" on public.preference_pairs for select to authenticated
    using(exists(select 1 from public.agent_feedback f where f.id=negative_feedback_id and f.auth_user_id=(select auth.uid())));
commit;
