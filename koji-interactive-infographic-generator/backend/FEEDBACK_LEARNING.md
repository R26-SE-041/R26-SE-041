# Feedback learning

The feedback system separates raw evidence from deployed model instructions.

## Lifecycle

1. A like or dislike is stored in `agent_feedback` with an agent-scoped output ID.
2. A dislike is sent back only to the responsible agent for a targeted retry.
3. When the corrected retry is liked, the two immutable records are linked in `preference_pairs`.
4. The weekly skill-evolution job aggregates controlled reason codes. Free-form comments are never promoted into prompts.
5. Repeated evidence creates a `memory_candidates` record:
   - 10 pairs from at least 3 sessions: agent Memento candidate.
   - 25 pairs from at least 5 sessions: agent Skill candidate.
   - Cross-agent candidates require evidence from at least 3 different agents.
6. Candidates remain `proposed` until the deployment/review policy approves them. Existing prompt-agent skill evolution still requires paired held-out evaluation before activation.

## Supabase + pgvector memory

`preference_pairs.context_embedding`, `user_preferences.embedding`, and `agent_memories.embedding` use the existing 384-dimensional `all-MiniLM-L6-v2` embedding space. HNSW cosine indexes support low-latency retrieval.

Runtime ranking combines semantic similarity (65%), confidence (25%), and evidence strength (10%). Hard filters are applied before ranking:

- Agent memories must be `deployed` and either global or assigned to the requested agent.
- Personal preferences must belong to the bearer-token user, match the agent, be `active`, and have memory enabled.
- Personal preferences require three idempotent accepted-retry pairs before activation.

Personal memory is opt-in. New users default to `memory_enabled = false`. The orchestrator verifies bearer tokens against Supabase Auth and derives the UUID from the verified session; body-provided user IDs are never trusted.

Memory API:

```text
POST /memory/context
GET  /memory/settings
POST /memory/settings
GET  /memory/preferences
POST /memory/preferences/{id}/revoke
POST /memory/clear
```

Authenticated endpoints require `Authorization: Bearer <supabase-access-token>`. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the orchestrator's `supabase-secret`.

Agent/global candidates are written to `agent_memories` with `proposed` status. Review and transition them without exposing an unauthenticated admin endpoint:

```powershell
python scripts/manage_memories.py list --status proposed
python scripts/manage_memories.py transition <memory-id> approved
python scripts/manage_memories.py transition <memory-id> deployed
```

Only `deployed` rows are eligible for runtime retrieval. Allowed transitions are enforced in the database helper: proposed → approved/rejected, approved → deployed/rejected, and deployed → superseded.

Global rules live in `config/global/`; agent-local rules live beside each agent. `MemoryManager` assembles global rules first, then local rules, while preserving the existing `skill_rules` and `memento` interface.

## Deployment

Before deploying the API, apply `scripts/create_tables.sql` to the Supabase database. Then redeploy the changed services from `backend/`:

```powershell
modal deploy orchestrator/modal_app.py
modal deploy agents/prompt-agent/modal_app.py
modal deploy agents/image-agent/modal_app.py
modal deploy agents/interactive-agent/modal_app.py
modal deploy agents/eval-agent/modal_app.py
modal deploy agents/skill-generator/modal_app.py
```

The frontend must set `EXPO_PUBLIC_BACKEND_HEALTH_URL` to the orchestrator base URL. It uses that base for `/health`, `/feedback`, and anonymous global/agent memory retrieval. To activate personal memory, the hosting application must pass its Supabase access token as the bearer token on feedback and memory calls.

The Expo root component accepts this token as `accessToken`. When present, the personal-memory panel exposes opt-in/out, review, per-preference forget, and two-step clear-all controls. Token acquisition remains the responsibility of the host application's Supabase Auth login flow; no access token is stored in Markdown, feedback records, or application configuration.

## Safety properties

- A preference pair must use the same session and agent and must link a dislike to a like.
- Dislikes require a reason; the UI also requires a reason for likes.
- Output snapshots are size-limited and image base64 is not copied into feedback storage.
- Regeneration never weakens deterministic safety checks.
- Upstream regeneration invalidates dependent frontend artifacts instead of reusing stale interactive or 3D output.
