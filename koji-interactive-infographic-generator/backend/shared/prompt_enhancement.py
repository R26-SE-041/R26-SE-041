"""Small deterministic safeguards for prompt enhancement quality."""

from __future__ import annotations

import re


def ensure_useful_enhancement(raw_prompt: str, candidate: str) -> str:
    """Keep a useful model enhancement or add a concise visual treatment.

    This intentionally avoids subject-specific templates. The user's subject,
    viewpoint, audience, and wording stay intact for any educational domain.
    """
    raw = re.sub(r"\s+", " ", raw_prompt).strip()
    enhanced = re.sub(r"\s+", " ", candidate).strip()
    raw_words = raw.casefold().split()
    enhanced_words = enhanced.casefold().split()
    meaningfully_expanded = (
        enhanced.casefold() != raw.casefold()
        and len(enhanced_words) >= len(raw_words) + 5
    )
    if meaningfully_expanded:
        return enhanced
    return (
        f"Create a clear, accurate educational illustration of {raw}. "
        "Preserve the requested subject, viewpoint, and audience. Use an uncluttered textbook-style "
        "composition, appropriate visual detail, coherent spatial relationships, and a clean neutral "
        "background. Do not embed text, labels, arrows, or watermarks in the image."
    )
