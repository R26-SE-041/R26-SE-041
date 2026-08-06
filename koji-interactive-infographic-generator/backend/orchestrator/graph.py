"""
orchestrator/graph.py
──────────────────────
LangGraph pipeline definition.

Graph: START → prompt_node → image_node → eval_node → db_node → END

Each node:
  - Receives the full PipelineState
  - Makes an HTTP request to its corresponding Modal-deployed agent endpoint
  - Returns a PARTIAL dict (only the keys it sets); LangGraph merges it back
  - NEVER raises — errors are captured in state["error"] and the graph continues

WHY HTTP (not modal.Function.lookup):
  The agents are separate Modal Apps, each with their own deploy lifecycle.
  HTTP endpoints are also the contract your teammates call — using the same
  interface here means the orchestrator is a true integration test of the REST API.

Timeouts:
  prompt_node :  90s  (LLM inference on T4)
  image_node  : 360s  (FLUX generation on A10G — can take 60-90s cold)
  eval_node   : 150s  (VLM + CLIPScore on A10G)
  db_node     :  10s  (simple Postgres write)
"""

from __future__ import annotations

import base64
import os
from typing import Any

import requests
from langgraph.graph import END, START, StateGraph

from shared.state import PipelineState


# ── Node: prompt enhancement ──────────────────────────────────────────────────

def prompt_node(state: PipelineState) -> dict[str, Any]:
    """Call prompt-agent /enhance and merge results into state."""
    url = os.environ["PROMPT_AGENT_URL"].rstrip("/") + "/enhance"
    try:
        resp = requests.post(
            url,
            json={"raw_prompt": state["raw_prompt"]},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "enhanced_prompt": data.get("enhanced_prompt"),
            "prompt_parse_error": data.get("prompt_parse_error", False),
            # Carry forward agent-level error without aborting pipeline
            "error": data.get("error"),
        }
    except requests.exceptions.Timeout:
        return {"error": "prompt-agent timed out after 90s", "prompt_parse_error": False}
    except Exception as exc:
        return {"error": f"prompt-agent call failed: {exc}", "prompt_parse_error": False}


# ── Node: image generation ────────────────────────────────────────────────────

def image_node(state: PipelineState) -> dict[str, Any]:
    """Call image-agent /generate and merge raw image bytes into state."""
    url = os.environ["IMAGE_AGENT_URL"].rstrip("/") + "/generate"
    try:
        # image-agent expects a single "prompt" key — use enhanced if available
        best_prompt = (
            state.get("enhanced_prompt")
            or state.get("raw_prompt")
            or ""
        )
        resp = requests.post(
            url,
            json={
                "prompt": best_prompt,
                "speed_mode": state.get("speed_mode", "pro"),
            },
            timeout=360,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            return {"image_bytes": None, "error": data["error"]}

        # Decode base64 → bytes for in-process handoff to eval_node
        # (eval agent re-encodes for its VLM call — this is intentional)
        b64 = data.get("image_base64", "")
        image_bytes = base64.b64decode(b64) if b64 else None

        return {"image_bytes": image_bytes, "error": state.get("error")}

    except requests.exceptions.Timeout:
        return {"image_bytes": None, "error": "image-agent timed out after 360s"}
    except Exception as exc:
        return {"image_bytes": None, "error": f"image-agent call failed: {exc}"}


# ── Node: evaluation ──────────────────────────────────────────────────────────

def eval_node(state: PipelineState) -> dict[str, Any]:
    """
    Call eval-agent /evaluate.
    Skips the call entirely if image_bytes is missing (don't call the agent
    with a guaranteed-to-fail payload — it would return a misleading 422).
    """
    url = os.environ["EVAL_AGENT_URL"].rstrip("/") + "/evaluate"

    image_bytes = state.get("image_bytes")
    if not image_bytes:
        return {
            "clip_score": None,
            "vlm_score": None,
            "vlm_feedback": None,
            "error": (state.get("error") or "Image generation failed — eval skipped"),
        }

    try:
        resp = requests.post(
            url,
            json={
                "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
                "enhanced_prompt": state.get("enhanced_prompt"),
                "raw_prompt": state["raw_prompt"],
            },
            timeout=150,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "clip_score": data.get("clip_score"),
            "vlm_score": data.get("vlm_score"),
            "vlm_feedback": data.get("vlm_feedback"),
            "error": data.get("error") or state.get("error"),
        }

    except requests.exceptions.Timeout:
        return {
            "clip_score": None,
            "vlm_score": None,
            "vlm_feedback": None,
            "error": "eval-agent timed out after 150s",
        }
    except Exception as exc:
        return {
            "clip_score": None,
            "vlm_score": None,
            "vlm_feedback": None,
            "error": f"eval-agent call failed: {exc}",
        }


# ── Node: database persistence ────────────────────────────────────────────────

def db_node(state: PipelineState) -> dict[str, Any]:
    """
    Persist the full pipeline run to Supabase.
    Inserts the record and returns the UUID as db_record_id.
    DB errors do NOT fail the pipeline — the result is still returned to the caller.
    """
    from shared.db import insert_pipeline_record, update_pipeline_record

    existing_err = state.get("error")
    try:
        record_id = insert_pipeline_record(
            raw_prompt=state["raw_prompt"],
            enhanced_prompt=state.get("enhanced_prompt"),
            prompt_parse_err=state.get("prompt_parse_error", False),
            error=existing_err,
        )

        update_pipeline_record(
            record_id=record_id,
            image_data=state.get("image_bytes"),
            clip_score=state.get("clip_score"),
            vlm_score=state.get("vlm_score"),
            vlm_feedback=state.get("vlm_feedback"),
            error=existing_err,
        )

        return {"db_record_id": record_id}

    except Exception as exc:
        # DB failure is non-fatal — preserve existing error or set warning
        db_msg = f"DB write failed: {exc}"
        return {"db_record_id": None, "error": f"{existing_err}; {db_msg}" if existing_err else db_msg}


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph() -> Any:
    """
    Compile and return the LangGraph pipeline.
    Call once at orchestrator startup and reuse the compiled graph.
    """
    g = StateGraph(PipelineState)

    g.add_node("prompt", prompt_node)
    g.add_node("image", image_node)
    g.add_node("eval", eval_node)
    g.add_node("db", db_node)

    g.add_edge(START, "prompt")
    g.add_edge("prompt", "image")
    g.add_edge("image", "eval")
    g.add_edge("eval", "db")
    g.add_edge("db", END)

    return g.compile()
