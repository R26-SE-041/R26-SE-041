"""Regression coverage for frontend-to-router document grounding."""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_voice_document_test_page_explicitly_requests_rag():
    """The /test document workflow must not silently fall through to general_base."""
    source = (REPO_ROOT / "frontend" / "src" / "app" / "test" / "page.tsx").read_text(
        encoding="utf-8-sig"
    )
    call = re.search(
        r"const answer = await askDocument\((.*?)\n\s*\)",
        source,
        flags=re.DOTALL,
    )

    assert call is not None
    assert re.search(r"detectedLanguage,\s*true,", call.group(1))
