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
import time
import uuid
from collections.abc import Callable
from typing import Any

import requests
from langgraph.graph import END, START, StateGraph

from shared.state import PipelineState


# ── Node: prompt enhancement ──────────────────────────────────────────────────

def prompt_node(state: PipelineState) -> dict[str, Any]:
    """Call prompt-agent /enhance and merge results into state."""
    url = os.environ["PROMPT_AGENT_URL"].rstrip("/") + "/enhance"
    config = state.get("experiment_config") or {}
    examples = state.get("memento_examples") or []
    if config.get("enable_memento", True) and not examples and state.get("retry_count", 0) == 0:
        try:
            from shared.memory import MemoryManager
            examples = MemoryManager().recall(state["raw_prompt"], limit=3)
        except Exception:
            examples = []
    try:
        resp = requests.post(
            url,
            json={
                "raw_prompt": state["raw_prompt"],
                "speed_mode": state.get("speed_mode", "pro"),
                "retry_feedback": state.get("retry_feedback"),
                "memento_examples": examples,
                "use_memento": config.get("enable_memento", True),
                "use_skill_rules": config.get("enable_skill_rules", True),
                "skill_rules_override": config.get("skill_rules_override"),
                "seed": config.get("seed"),
                "skill_compression_mode": state.get("skill_compression_mode", "auto"),
                "skill_token_budget": state.get("skill_token_budget", 150),
                "available_context_tokens": state.get("available_context_tokens"),
                "model_variant": config.get("prompt_model_variant", "base"),
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "enhanced_prompt": data.get("enhanced_prompt"),
            "anatomy_spec": data.get("anatomy_spec") or {"is_anatomy": False},
            "model_variants": {
                **(state.get("model_variants") or {}),
                "prompt": data.get("model_variant", config.get("prompt_model_variant", "base")),
            },
            "prompt_parse_error": data.get("prompt_parse_error", False),
            "memento_examples": examples,
            "skill_compression": data.get("skill_compression") or {},
            "safety": data.get("safety") or {},
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
    config = state.get("experiment_config") or {}
    safety = state.get("safety") or {}
    if state.get("error") or safety.get("allowed") is False:
        return {
            "image_bytes": None,
            "error": state.get("error") or "CONTENT_POLICY_BLOCKED: prompt failed safety review",
        }
    if not state.get("enhanced_prompt"):
        return {"image_bytes": None, "error": "IMAGE_PROMPT_MISSING: generation skipped"}
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
                "seed": (
                    int(config["seed"]) + int(state.get("retry_count", 0))
                    if config.get("seed") is not None else None
                ),
                "domain": "anatomy" if (state.get("anatomy_spec") or {}).get("is_anatomy") else "generic",
                "organ": (state.get("anatomy_spec") or {}).get("organ"),
                "view": (state.get("anatomy_spec") or {}).get("view"),
                "use_skill_rules": config.get("enable_skill_rules", True),
            },
            timeout=360,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            return {
                "image_bytes": None,
                "safety": data.get("safety") or state.get("safety") or {},
                "error": data["error"],
            }

        # Decode base64 → bytes for in-process handoff to eval_node
        # (eval agent re-encodes for its VLM call — this is intentional)
        b64 = data.get("image_base64", "")
        image_bytes = base64.b64decode(b64) if b64 else None

        return {
            "image_bytes": image_bytes,
            "model_variants": {
                **(state.get("model_variants") or {}),
                "image": data.get("model_variant", config.get("image_model_variant", "base")),
            },
            "error": state.get("error"),
        }

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
            "visual_score": None,
            "pedagogical_score": None,
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
                "anatomy_spec": state.get("anatomy_spec") or {"is_anatomy": False},
                "enable_anatomy_critic": (state.get("experiment_config") or {}).get("enable_anatomy_critic", True),
            },
            timeout=150,
        )
        resp.raise_for_status()
        data = resp.json()

        config = state.get("experiment_config") or {}
        visual_score = data.get("visual_score", data.get("vlm_score"))
        pedagogical_score = data.get("pedagogical_score", data.get("vlm_score"))
        if not config.get("enable_dual_critic", True):
            visual_score = data.get("vlm_score")
            pedagogical_score = data.get("vlm_score")

        return {
            "clip_score": data.get("clip_score"),
            "vlm_score": data.get("vlm_score"),
            "visual_score": visual_score,
            "pedagogical_score": pedagogical_score,
            "vlm_feedback": data.get("vlm_feedback"),
            "anatomy_metrics": data.get("anatomy_metrics") or {},
            "anatomy_hard_failures": data.get("anatomy_hard_failures") or [],
            "error": data.get("error") or state.get("error"),
        }

    except requests.exceptions.Timeout:
        return {
            "clip_score": None,
            "vlm_score": None,
            "visual_score": None,
            "pedagogical_score": None,
            "vlm_feedback": None,
            "error": "eval-agent timed out after 150s",
        }
    except Exception as exc:
        return {
            "clip_score": None,
            "vlm_score": None,
            "visual_score": None,
            "pedagogical_score": None,
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

    config = state.get("experiment_config") or {}
    if not config.get("persist_run", True):
        return {"db_record_id": None}

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
            visual_score=state.get("visual_score"),
            pedagogical_score=state.get("pedagogical_score"),
            vlm_feedback=state.get("vlm_feedback"),
            error=existing_err,
        )

        try:
            from shared.memory import MemoryManager
            if (
                config.get("enable_memento", True)
                and state.get("enhanced_prompt")
                and not state.get("anatomy_hard_failures")
            ):
                anatomy_spec = state.get("anatomy_spec") or {}
                MemoryManager().promote(
                    raw_prompt=state["raw_prompt"],
                    enhanced_prompt=state["enhanced_prompt"],
                    visual_score=float(state.get("visual_score") or 0),
                    pedagogical_score=float(state.get("pedagogical_score") or 0),
                    clip_score=state.get("clip_score"),
                    vlm_feedback=state.get("vlm_feedback"),
                    subject_tag=anatomy_spec.get("organ"),
                    grade_tag=anatomy_spec.get("grade_level"),
                    style_tag=anatomy_spec.get("view"),
                )
        except Exception:
            pass

        return {"db_record_id": record_id}

    except Exception as exc:
        # DB failure is non-fatal — preserve existing error or set warning
        db_msg = f"DB write failed: {exc}"
        return {"db_record_id": None, "error": f"{existing_err}; {db_msg}" if existing_err else db_msg}


# ── Graph assembly ────────────────────────────────────────────────────────────

def generate_retry_feedback(visual: float, pedagogical: float, notes: str | None) -> str:
    parts: list[str] = []
    if visual < 7.0:
        parts.append("VISUAL: Improve composition, legibility, colors, and layout.")
    if pedagogical < 7.0:
        parts.append("PEDAGOGICAL: Correct facts, add useful labels, and match the learner's level.")
    if notes:
        parts.append(f"Evaluator notes: {notes}")
    return " | ".join(parts)


def reflection_node(state: PipelineState) -> dict[str, Any]:
    """Store the best attempt and prepare feedback for at most two retries."""
    visual = float(state.get("visual_score") or 0)
    pedagogical = float(state.get("pedagogical_score") or 0)
    anatomy_failures = state.get("anatomy_hard_failures") or []
    current = {
        "visual_score": visual,
        "pedagogical_score": pedagogical,
        "clip_score": state.get("clip_score"),
        "vlm_score": state.get("vlm_score"),
        "vlm_feedback": state.get("vlm_feedback"),
        "enhanced_prompt": state.get("enhanced_prompt"),
        "image_bytes": state.get("image_bytes"),
        "anatomy_metrics": state.get("anatomy_metrics") or {},
        "anatomy_hard_failures": anatomy_failures,
    }
    best = state.get("best_attempt")
    best_total = (
        float(best.get("visual_score", 0)) + float(best.get("pedagogical_score", 0))
        - (20 if best.get("anatomy_hard_failures") else 0)
        if best else -1
    )
    current_total = visual + pedagogical - (20 if anatomy_failures else 0)
    if current_total > best_total:
        best = current

    retries = state.get("retry_count", 0)
    config = state.get("experiment_config") or {}
    accepted = (
        not config.get("enable_reflexion", True)
        or (visual >= 7.0 and pedagogical >= 7.0 and not anatomy_failures)
    )
    if accepted or retries >= 2 or not state.get("image_bytes"):
        assert best is not None
        return {
            "best_attempt": best,
            "enhanced_prompt": best.get("enhanced_prompt"),
            "image_bytes": best.get("image_bytes"),
            "clip_score": best.get("clip_score"),
            "vlm_score": best.get("vlm_score"),
            "visual_score": best.get("visual_score"),
            "pedagogical_score": best.get("pedagogical_score"),
            "vlm_feedback": best.get("vlm_feedback"),
            "anatomy_metrics": best.get("anatomy_metrics") or {},
            "anatomy_hard_failures": best.get("anatomy_hard_failures") or [],
            "retry_feedback": None,
        }
    return {
        "best_attempt": best,
        "retry_count": retries + 1,
        "retry_feedback": " | ".join(filter(None, [
            generate_retry_feedback(visual, pedagogical, state.get("vlm_feedback")),
            f"ANATOMY HARD FAILURES: {'; '.join(anatomy_failures)}" if anatomy_failures else "",
        ])),
        "error": None,
    }


def should_retry(state: PipelineState) -> str:
    config = state.get("experiment_config") or {}
    if not config.get("enable_reflexion", True):
        return "accept"
    if not state.get("retry_feedback"):
        return "accept"
    if (state.get("anatomy_spec") or {}).get("is_anatomy"):
        return "retry_image"
    return "retry_prompt"


def traced_node(name: str, node: Callable[[PipelineState], dict[str, Any]]) -> Callable[[PipelineState], dict[str, Any]]:
    """Wrap a graph node with structured latency and status telemetry."""
    def wrapped(state: PipelineState) -> dict[str, Any]:
        from shared.trace_logger import TraceLogger
        trace_id = state.get("trace_id") or str(uuid.uuid4())
        started = time.perf_counter()
        result = node(state)
        TraceLogger(trace_id=trace_id).event(
            name,
            status="error" if result.get("error") else "ok",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            retry_count=state.get("retry_count", 0),
        )
        result.setdefault("trace_id", trace_id)
        return result
    return wrapped


def build_graph() -> Any:
    """
    Compile and return the LangGraph pipeline.
    Call once at orchestrator startup and reuse the compiled graph.
    """
    g = StateGraph(PipelineState)

    g.add_node("prompt", traced_node("prompt", prompt_node))
    g.add_node("image", traced_node("image", image_node))
    g.add_node("eval", traced_node("eval", eval_node))
    g.add_node("reflect", traced_node("reflect", reflection_node))
    g.add_node("db", traced_node("db", db_node))

    g.add_edge(START, "prompt")
    g.add_edge("prompt", "image")
    g.add_edge("image", "eval")
    g.add_edge("eval", "reflect")
    g.add_conditional_edges(
        "reflect", should_retry, {"retry_prompt": "prompt", "retry_image": "image", "accept": "db"}
    )
    g.add_edge("db", END)

    return g.compile()
