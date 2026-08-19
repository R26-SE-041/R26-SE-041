---
name: evolve-agent-skills
description: Propose and deploy validation-gated improvements to an individual agent's SKILL.md. Use for feedback analysis, candidate generation, held-out evaluation, versioning, rollback-safe activation, and scheduled skill evolution.
---

# Skill evolution

- Evolve one named agent skill at a time; never merge memories across agents.
- Derive candidates only from repeated, high-confidence feedback patterns.
- Preserve all safety constraints in every candidate.
- Compare old and new rules on the same held-out prompts and seeds.
- Deploy only a measured improvement; retain the last known-good version otherwise.
- Do not promote raw conversations into a skill or memento.
