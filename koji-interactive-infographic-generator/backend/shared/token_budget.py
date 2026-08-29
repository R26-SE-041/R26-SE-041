"""Small, dependency-free context budgeting helpers for agent prompts."""

from __future__ import annotations

import re
from collections.abc import Mapping


def estimate_tokens(text: str) -> int:
    """Return a conservative tokenizer-independent token estimate."""
    return max(0, (len(text) + 3) // 4)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def dedup_context(items: list[str], threshold: float = 0.85) -> list[str]:
    """Remove near-duplicate context blocks using lexical Jaccard overlap."""
    kept: list[str] = []
    signatures: list[set[str]] = []
    for item in items:
        clean = item.strip()
        if not clean:
            continue
        signature = _words(clean)
        duplicate = False
        for existing in signatures:
            union = signature | existing
            if union and len(signature & existing) / len(union) >= threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(clean)
            signatures.append(signature)
    return kept


def enforce_budget(text: str, max_tokens: int) -> str:
    """Truncate text without splitting the final word."""
    if max_tokens <= 0:
        return ""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    shortened = text[:max_chars].rsplit(" ", 1)[0].rstrip()
    return f"{shortened}…" if shortened else text[:max_chars]


class TokenBudgetController:
    """Assemble named prompt sections within stable per-agent budgets."""

    BUDGETS: dict[str, dict[str, int]] = {
        "prompt_agent": {
            "system": 150,
            "skill_rules": 150,
            "memento": 200,
            "retry_feedback": 100,
            "user_prompt": 100,
        },
        "interactive_agent": {
            "system": 100,
            "skill_rules": 140,
            "memento": 80,
            "rag_context": 300,
            "web_fallback": 200,
            "mode_instruction": 50,
            "user_question": 50,
            "retry_feedback": 100,
        },
        "eval_agent": {
            "system": 100,
            "skill_rules": 140,
            "memento": 80,
            "generation_prompt": 220,
            "output_schema": 100,
        },
    }

    def assemble(
        self,
        agent: str,
        sections: Mapping[str, str],
        budget_overrides: Mapping[str, int] | None = None,
    ) -> str:
        if agent not in self.BUDGETS:
            raise ValueError(f"Unknown agent budget: {agent}")
        blocks: list[str] = []
        overrides = budget_overrides or {}
        for name, default_limit in self.BUDGETS[agent].items():
            limit = max(0, int(overrides.get(name, default_limit)))
            value = sections.get(name, "").strip()
            if value:
                blocks.append(enforce_budget(value, limit))
        return "\n\n".join(dedup_context(blocks))
