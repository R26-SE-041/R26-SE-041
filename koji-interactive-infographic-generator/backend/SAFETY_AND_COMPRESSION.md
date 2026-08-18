# Safety and semantic compression

The public orchestrator supports token-aware Qwen compression of the prompt
agent's `SKILL.md` context and layered prompt safety checks.

## Compression controls

Include these optional fields in `POST /generate`:

```json
{
  "prompt": "Create an infographic about photosynthesis",
  "skill_compression_mode": "auto",
  "skill_token_budget": 150,
  "available_context_tokens": 800
}
```

- `auto` compresses when the skill exceeds its budget or available context is
  at/below the low-token threshold.
- `always` manually forces Qwen compression.
- `off` skips semantic compression; the normal hard token cap still applies.
- `skill_token_budget` accepts 40–600 tokens.
- `available_context_tokens` is optional. Values at or below 900 trigger the
  low-token path and may reduce the effective skill budget further.

The response includes `skill_compression` metadata showing whether compression
was applied, why, the method used, and estimated before/after token counts.
Compressed results are cached per SKILL content hash and token target. If Qwen
compression fails validation, a deterministic Markdown compactor is used.

## Safety behaviour

Safety policy is enforced outside `SKILL.md`; skill rules are guidance and are
not the security boundary.

1. A deterministic pre-check rejects high-confidence unsafe prompts.
2. Qwen performs contextual classification so benign educational, medical,
   historical, prevention, and legal-awareness prompts can remain allowed.
3. The enhanced output is checked again by both layers.
4. The orchestrator stops before image generation when prompt review fails.
5. The image agent independently performs CPU and GPU-side deterministic checks.

Blocked requests return no image and an error beginning with
`CONTENT_POLICY_BLOCKED`, plus structured `safety` metadata. The system blocks
instead of silently rewriting unsafe intent.

Contextual moderation is fail-closed: if Qwen cannot return a valid moderation
decision, the request is stopped with category `safety_review` rather than sent
to the image model.

The automatic SKILL evolution validator requires a `Safety Rules` section, so a
generated skill version cannot deploy after dropping the safety policy.
