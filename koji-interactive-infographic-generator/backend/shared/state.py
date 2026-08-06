"""
shared/state.py
───────────────
Single typed state schema for the entire LangGraph pipeline.

RULE: Every agent node MUST import this and type its input/output against it.
      Never use raw dict[str, Any] as a node return type — that bypasses
      LangGraph's merge logic and silently drops keys.
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict):
    """
    The one and only state object that flows through the LangGraph pipeline.

    Lifecycle:
      raw_prompt         → set by the caller (orchestrator entry point)
      enhanced_prompt    → set by prompt-agent node
      prompt_parse_error → set by prompt-agent node; True means JSON retry exhausted
      image_bytes        → set by image-agent node (raw PNG bytes)
      clip_score         → set by eval-agent node
      vlm_score          → set by eval-agent node (0–10 float from Qwen2.5-VL)
      vlm_feedback       → set by eval-agent node (natural-language feedback string)
      db_record_id       → set by db node after persisting the run
      error              → set by any node on pipeline-level failure; None = success
    """

    raw_prompt: str
    enhanced_prompt: Optional[str]
    prompt_parse_error: bool
    image_bytes: Optional[bytes]
    clip_score: Optional[float]
    vlm_score: Optional[float]
    vlm_feedback: Optional[str]
    db_record_id: Optional[str]
    error: Optional[str]
    speed_mode: str  # "normal" | "pro" | "promax" — controls GPU tier routing


def initial_state(raw_prompt: str) -> PipelineState:
    """Construct a fully-initialised PipelineState from a raw user prompt."""
    return PipelineState(
        raw_prompt=raw_prompt,
        enhanced_prompt=None,
        prompt_parse_error=False,
        image_bytes=None,
        clip_score=None,
        vlm_score=None,
        vlm_feedback=None,
        db_record_id=None,
        error=None,
        speed_mode="pro",
    )
