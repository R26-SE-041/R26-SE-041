"""Typed prompt policies for the FLUX image agent.

FLUX does not consume PERSONA/SKILL files directly.  The application selects
one explicit policy and supplies the resulting text prompt to the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ImageDomain = Literal["generic", "anatomy"]


@dataclass(frozen=True)
class ImagePromptPolicy:
    domain: ImageDomain
    policy_id: str
    mandatory_suffix: str = ""

    def apply(self, prompt: str, *, memory_context: str = "", feedback: str = "") -> str:
        """Compose model input while keeping mandatory rules at highest priority."""
        sections = [prompt.strip()]
        if memory_context.strip():
            sections.append(f"Validated relevant generation preferences: {memory_context.strip()}")
        if feedback.strip():
            sections.append(
                "User-requested corrections for this retry: "
                f"{feedback.strip()}. Preserve all correct educational content and the original learning objective."
            )
        if self.mandatory_suffix:
            sections.append(self.mandatory_suffix)
        return "\n\n".join(section for section in sections if section)


GENERIC_POLICY = ImagePromptPolicy(
    domain="generic",
    policy_id="generic-preserve-intent-v1",
)

ANATOMY_POLICY = ImagePromptPolicy(
    domain="anatomy",
    policy_id="anatomy-clean-base-v1",
    mandatory_suffix=(
        "FINAL ANATOMY OUTPUT RULES: preserve the requested anatomical view and subject; show one "
        "isolated human anatomical subject on a white or very light neutral background; do not render "
        "text, labels, letters, numbers, arrows, legends, captions, callouts, borders, watermarks, "
        "decorative objects, an unrequested torso, or unrelated anatomy. These rules override conflicting correction "
        "notes or recalled preferences."
    ),
)


def select_image_policy(domain: ImageDomain) -> ImagePromptPolicy:
    """Return the only policy allowed for the validated request domain."""
    return ANATOMY_POLICY if domain == "anatomy" else GENERIC_POLICY
