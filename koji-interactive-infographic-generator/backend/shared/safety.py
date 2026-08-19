"""Dependency-free prompt safety gate shared by prompt and image agents.

This is a high-confidence first/last line of defence. The prompt agent adds a
contextual Qwen classification between these deterministic checks.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    category: str = "safe"
    reason: str = "Prompt passed the safety gate"
    source: str = "rules"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_MINOR = re.compile(r"\b(child|children|kid|kids|minor|underage|teenager|schoolgirl|schoolboy)\b", re.I)
_SEXUAL = re.compile(
    r"\b(explicit sex|sexual act|porn(?:ography)?|nude|nudity|naked|genitals?|fetish|erotic)\b",
    re.I,
)
_EXPLICIT = re.compile(
    r"(?:\b18\s*\+|\bgraphic sexual|\bexplicit sexual|\bporn(?:ographic)?|\berotic nude|\bsexual intercourse)",
    re.I,
)
_ILLEGAL_ACTION = re.compile(
    r"\b(how to|instructions? (?:for|to)|step[- ]by[- ]step|build|manufacture|synthesize|"
    r"hack|steal|bypass|evade|hide|traffic|forge)\b",
    re.I,
)
_HIGH_RISK_ACTION = re.compile(
    r"\b(build|manufacture|synthesize|hack|steal|bypass|evade|traffic|forge)\b",
    re.I,
)
_ILLEGAL_TARGET = re.compile(
    r"\b(bomb|explosive|meth(?:amphetamine)?|illegal drugs?|malware|ransomware|passwords?|"
    r"credit cards?|identity theft|counterfeit|weapon|firearm|law enforcement)\b",
    re.I,
)
_BENIGN_CONTEXT = re.compile(
    r"\b(education(?:al)?|medical|biology|anatomy|health|prevention|awareness|safety|history|"
    r"news|law|legal|ethics|dangers?|harms?|recovery|treatment)\b",
    re.I,
)


def assess_prompt(prompt: str) -> SafetyDecision:
    """Block explicit sexual content and actionable facilitation of illegal harm."""
    clean = re.sub(r"\s+", " ", prompt).strip()
    if not clean:
        return SafetyDecision(False, "invalid", "Prompt is empty")

    if _MINOR.search(clean) and _SEXUAL.search(clean):
        return SafetyDecision(False, "sexual_minors", "Sexual content involving minors is not allowed")
    if _EXPLICIT.search(clean):
        return SafetyDecision(False, "sexual", "Explicit sexual or pornographic content is not allowed")

    has_illegal_target = _ILLEGAL_TARGET.search(clean)
    actionable_illegal = has_illegal_target and (
        _HIGH_RISK_ACTION.search(clean)
        or (_ILLEGAL_ACTION.search(clean) and not _BENIGN_CONTEXT.search(clean))
    )
    if actionable_illegal:
        return SafetyDecision(False, "illegal", "Actionable assistance for illegal activity is not allowed")

    # Non-explicit anatomy, health, prevention, history, and legal-awareness
    # prompts remain eligible for contextual Qwen review.
    if _SEXUAL.search(clean) and not _BENIGN_CONTEXT.search(clean):
        return SafetyDecision(False, "sexual", "Adult sexualized content is not allowed")
    return SafetyDecision(True)


def model_decision(payload: dict[str, Any] | None) -> SafetyDecision | None:
    """Validate a Qwen classifier response; invalid output cannot override rules."""
    if not isinstance(payload, dict) or not isinstance(payload.get("allowed"), bool):
        return None
    category = str(payload.get("category") or "safe").strip().lower()
    allowed_categories = {"safe", "sexual", "sexual_minors", "illegal"}
    if category not in allowed_categories:
        return None
    allowed = bool(payload["allowed"])
    if not allowed and category == "safe":
        return None
    reason = str(payload.get("reason") or "Prompt failed contextual safety review")[:240]
    return SafetyDecision(allowed, category, reason, "qwen")


def blocked_error(decision: SafetyDecision) -> str:
    return f"CONTENT_POLICY_BLOCKED[{decision.category}]: {decision.reason}"
