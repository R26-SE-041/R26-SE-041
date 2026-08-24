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

# Broad biological / anatomical subject regex — used to deterministically
# allow benign educational prompts before a probabilistic model gets a vote.
_BIOLOGY_SUBJECT = re.compile(
    r"\b(brain|heart|lungs?|liver|kidney|kidneys|eye|eyes|skin|stomach|intestin(?:e|es|al)|"
    r"skull|spine|spinal|muscle|bone|joint|tendon|ligament|artery|arter(?:y|ies|ial)|"
    r"vein|veins?|aorta|ventricle|atrium|cortex|cerebr(?:um|al|ellum)|lobe|neuron|"
    r"organ|cell|tissue|membrane|nucleus|chromosome|dna|rna|mitosis|meiosis|"
    r"anatomy|anatomical|dissect(?:ion)?|cross[- ]?section|cutaway|sagittal|coronal|"
    r"transverse|axial|anterior|posterior|dorsal|ventral|lateral|medial|"
    r"histolog(?:y|ical)|physiolog(?:y|ical)|morpholog(?:y|ical)|"
    r"photosynthesis|ecosystem|biome|organism|species|genus|"
    r"illustration|diagram|textbook|infographic|educational)\b",
    re.I,
)


def is_benign_biology(prompt: str) -> bool:
    """Deterministically identify benign biology/anatomy/educational prompts.

    These prompts must never be sent to a probabilistic classifier because a
    3B model can randomly misclassify normal anatomy terms (e.g. "brain") as
    illegal content.  Only prompts that also match an explicit harmful target
    remain eligible for contextual review.
    """
    clean = re.sub(r"\s+", " ", prompt).strip()
    if not _BIOLOGY_SUBJECT.search(clean):
        return False
    # If an illegal *target* is explicitly present alongside biology language,
    # this is ambiguous and should NOT be short-circuited as benign.
    if _ILLEGAL_TARGET.search(clean):
        return False
    # Sexual language combined with biology is also ambiguous.
    if _SEXUAL.search(clean) or _EXPLICIT.search(clean):
        return False
    return True


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


def needs_contextual_review(prompt: str) -> bool:
    """Return whether a rules-safe prompt still contains ambiguous risk language.

    The model classifier is useful for genuinely ambiguous context, but it must
    not get a random veto over ordinary educational requests such as anatomy.

    Benign biology/anatomy prompts are deterministically allowed — they must
    never be sent to a probabilistic classifier that can randomly block "brain"
    as illegal.
    """
    clean = re.sub(r"\s+", " ", prompt).strip()
    # Short-circuit: clear biology/anatomy with no illegal targets or sexual
    # language is unambiguously benign.
    if is_benign_biology(clean):
        return False
    return bool(
        _MINOR.search(clean)
        or _SEXUAL.search(clean)
        or _EXPLICIT.search(clean)
        or _ILLEGAL_ACTION.search(clean)
        or _ILLEGAL_TARGET.search(clean)
    )


def is_model_generated_safe(prompt: str) -> SafetyDecision:
    """Safety check for model-generated output (enhanced prompts).

    Model output should only be checked with deterministic rules, never re-run
    through the probabilistic Qwen classifier.  This prevents the circular
    false-positive where Qwen generates a prompt containing words like "build"
    or "textbook", needs_contextual_review() triggers, and Qwen then
    misclassifies its own output as illegal.
    """
    return assess_prompt(prompt)


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
