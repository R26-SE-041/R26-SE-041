"""Token-aware semantic compression helpers for prompt-agent skill rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from shared.token_budget import enforce_budget, estimate_tokens


CompressionMode = Literal["auto", "always", "off"]


@dataclass(frozen=True)
class CompressionPlan:
    should_compress: bool
    target_tokens: int
    reason: str


def plan_compression(
    text: str,
    mode: CompressionMode = "auto",
    target_tokens: int = 150,
    available_context_tokens: int | None = None,
    low_token_threshold: int = 900,
) -> CompressionPlan:
    """Choose whether Qwen should compress rules before prompt assembly."""
    if mode not in {"auto", "always", "off"}:
        raise ValueError(f"Unsupported compression mode: {mode}")
    if target_tokens < 40:
        raise ValueError("target_tokens must be at least 40")

    effective_target = target_tokens
    if available_context_tokens is not None and available_context_tokens <= low_token_threshold:
        effective_target = min(target_tokens, max(40, available_context_tokens // 6))

    source_tokens = estimate_tokens(text)
    if mode == "off":
        return CompressionPlan(False, effective_target, "disabled")
    if mode == "always":
        return CompressionPlan(True, effective_target, "manual")
    if available_context_tokens is not None and available_context_tokens <= low_token_threshold:
        return CompressionPlan(True, effective_target, "low_context_tokens")
    if source_tokens > effective_target:
        return CompressionPlan(True, effective_target, "skill_over_budget")
    return CompressionPlan(False, effective_target, "within_budget")


def fallback_compress_markdown(markdown: str, target_tokens: int) -> str:
    """Deterministically retain headings and concise rules if Qwen compression fails."""
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("version:"):
            continue
        if line.startswith("#") or re.match(r"^[-*]\s+", line):
            lines.append(line)
    compact = "\n".join(lines) if lines else markdown.strip()
    return enforce_budget(compact, target_tokens)
