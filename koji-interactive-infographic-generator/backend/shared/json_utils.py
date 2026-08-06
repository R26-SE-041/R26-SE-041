"""
shared/json_utils.py
────────────────────
Robust JSON parsing with LLM retry logic.

WHY THIS EXISTS:
  LLMs (including Qwen2.5-3B) frequently output:
    - Markdown code fences: ```json { ... } ```
    - Trailing commas
    - Extra prose before/after the JSON object
    - Partial/truncated JSON on long outputs

  A naked json.loads() will crash on any of the above.
  This module strips fences, attempts parsing, and re-prompts
  the LLM with an explicit correction instruction on failure.

IMPORT PATTERN (in each Modal agent):
  The shared/ directory is added to the Modal image via
  image.add_local_python_source("shared") — see each modal_app.py.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, Optional


_FENCE_SEARCH = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")


def strip_json_fence(text: str) -> str:
    """
    Remove Markdown code fences and surrounding prose from LLM output.

    Handles:
      - ```json { ... } ```
      - Prose before/after markdown code fences
      - Bare JSON objects embedded in conversational text
    """
    text = text.strip()
    match = _FENCE_SEARCH.search(text)
    if match:
        return match.group(1).strip()

    # Fallback: find outermost curly braces if LLM output includes leading/trailing prose
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        return text[start : end + 1].strip()

    return text


def parse_json_with_retry(
    raw_output: str,
    llm_fn: Callable[[str], str],
    correction_prompt: str,
    max_retries: int = 2,
) -> tuple[Optional[dict[str, Any]], bool]:
    """
    Attempt to parse `raw_output` as JSON with up to `max_retries` correction rounds.

    Args:
        raw_output:        The raw string produced by the LLM.
        llm_fn:            A callable that takes a prompt str and returns a str response.
                           Used to re-prompt the model with a correction instruction.
        correction_prompt: Context given to the LLM when asking it to fix its output.
        max_retries:       Number of additional LLM calls allowed before giving up.

    Returns:
        (parsed_dict, had_error)
          - parsed_dict:  The parsed dict on success, or None on exhausted retries.
          - had_error:    False if parsing succeeded on the first or a retry attempt,
                          True if all retries were exhausted.

    Caller contract:
        On (None, True), fall back gracefully — do NOT raise. Set
        prompt_parse_error=True in the pipeline state and continue.
    """
    attempt = strip_json_fence(raw_output)

    for i in range(max_retries + 1):
        try:
            return json.loads(attempt), False
        except json.JSONDecodeError:
            if i < max_retries:
                correction = (
                    f"{correction_prompt}\n\n"
                    f"Your previous output was not valid JSON:\n{attempt}\n\n"
                    "Output ONLY a raw JSON object. "
                    "No markdown, no prose, no code fences. Start with {{ and end with }}."
                )
                attempt = strip_json_fence(llm_fn(correction))
            # else: fall through to return (None, True)

    return None, True
