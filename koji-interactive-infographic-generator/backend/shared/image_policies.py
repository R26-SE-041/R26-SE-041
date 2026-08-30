"""Versioned, executable runtime policies for the FLUX image agent.

This module is the image agent's source of truth. Behaviour is represented as
typed data and tested code instead of Markdown that diffusion cannot execute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ImageDomain = Literal["generic", "anatomy"]

POLICY_VERSION = "image-runtime-v2"
IMAGE_HEIGHT = 512
IMAGE_WIDTH = 512
NUM_INFERENCE_STEPS = 25
GUIDANCE_SCALE = 3.5
MAX_CONTEXT_CHARS = 2_000


def _clean_context(value: str) -> str:
    """Bound optional runtime context and remove control-character noise."""
    printable = "".join(char for char in value if char in "\n\t" or ord(char) >= 32)
    return " ".join(printable.split())[:MAX_CONTEXT_CHARS]


@dataclass(frozen=True)
class ImagePromptPolicy:
    domain: ImageDomain
    policy_id: str
    mandatory_suffix: str = ""

    def apply(
        self,
        prompt: str,
        *,
        memory_context: str = "",
        feedback: str = "",
        apply_domain_rules: bool = True,
    ) -> str:
        """Compose model input while keeping mandatory rules at highest priority."""
        sections = [prompt.strip()]
        memory_context = _clean_context(memory_context)
        feedback = _clean_context(feedback)
        if memory_context:
            sections.append(f"Validated relevant generation preferences: {memory_context}")
        if feedback:
            sections.append(
                "User-requested corrections for this retry: "
                f"{feedback.strip()}. Preserve all correct educational content and the original learning objective."
            )
        if apply_domain_rules and self.mandatory_suffix:
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
