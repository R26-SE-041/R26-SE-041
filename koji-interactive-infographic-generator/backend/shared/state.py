"""
shared/state.py
───────────────
Single typed state schema for the entire LangGraph pipeline.

RULE: Every agent node MUST import this and type its input/output against it.
      Never use raw dict[str, Any] as a node return type — that bypasses
      LangGraph's merge logic and silently drops keys.
"""

from __future__ import annotations

import uuid

from typing import Any, Optional
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
    enhanced_prompt_json: Optional[dict[str, Any]]
    anatomy_spec: dict[str, Any]
    routing: dict[str, Any]
    model_variants: dict[str, str]
    prompt_parse_error: bool
    image_bytes: Optional[bytes]
    clip_score: Optional[float]
    vlm_score: Optional[float]
    visual_score: Optional[float]
    pedagogical_score: Optional[float]
    anatomy_metrics: dict[str, Any]
    anatomy_hard_failures: list[str]
    vlm_feedback: Optional[str]
    retry_count: int
    retry_feedback: Optional[str]
    best_attempt: Optional[dict[str, Any]]
    memento_examples: list[dict[str, Any]]
    token_usage: dict[str, int]
    safety: dict[str, Any]
    trace_id: Optional[str]
    experiment_config: dict[str, Any]
    db_record_id: Optional[str]
    error: Optional[str]
    speed_mode: str  # "normal" | "pro" | "promax" — controls GPU tier routing


def initial_state(
    raw_prompt: str,
    experiment_config: dict[str, Any] | None = None,
) -> PipelineState:
    """Construct a fully-initialised PipelineState from a raw user prompt."""
    return PipelineState(
        raw_prompt=raw_prompt,
        enhanced_prompt=None,
        enhanced_prompt_json=None,
        anatomy_spec={"is_anatomy": False},
        routing={},
        model_variants={"prompt": "base", "image": "base", "interactive": "base"},
        prompt_parse_error=False,
        image_bytes=None,
        clip_score=None,
        vlm_score=None,
        visual_score=None,
        pedagogical_score=None,
        anatomy_metrics={},
        anatomy_hard_failures=[],
        vlm_feedback=None,
        retry_count=0,
        retry_feedback=None,
        best_attempt=None,
        memento_examples=[],
        token_usage={},
        safety={},
        trace_id=str(uuid.uuid4()),
        experiment_config=experiment_config or {},
        db_record_id=None,
        error=None,
        speed_mode="pro",
    )
