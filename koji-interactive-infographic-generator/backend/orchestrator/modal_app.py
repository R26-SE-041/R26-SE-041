"""
orchestrator/modal_app.py
──────────────────────────
Image Generation Orchestrator
  - Exposes the public REST API consumed by frontend and teammate services
  - Runs on Modal WITHOUT GPU (CPU-only) — all heavy lifting is delegated
    to individual agent endpoints
  - Builds and runs the LangGraph pipeline on each request

REQUIRED MODAL SECRETS (create before deploy):
  modal secret create agent-urls-secret \
      PROMPT_AGENT_URL=<deployed-prompt-agent-url> \
      IMAGE_AGENT_URL=<deployed-image-agent-url> \
      EVAL_AGENT_URL=<deployed-eval-agent-url>

  modal secret create supabase-secret \
      DATABASE_URL=postgresql://user:password@host:5432/dbname

DEPLOY (from backend/ directory):
    cd backend
    modal deploy orchestrator/modal_app.py

REST CONTRACT: see README.md
"""

from __future__ import annotations

import base64
from typing import Literal

import modal

# ── Modal App ─────────────────────────────────────────────────────────────────

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
        "requests>=2.32.0",
        "psycopg2-binary>=2.9.9",
        "typing_extensions>=4.12.0",
        "sentence-transformers>=3.2.0",
    )
    # Run `modal deploy` from backend/ so both source paths resolve correctly
    .add_local_python_source("shared")
    .add_local_python_source("orchestrator")
)

app = modal.App("image-gen-orchestrator", image=image)

# ── FastAPI + LangGraph ───────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

web_app = FastAPI(
    title="Image Generation Orchestrator",
    description=(
        "AI-Powered Educational Image Generation — REST API.\n\n"
        "Orchestrates: prompt-agent → image-agent → eval-agent → Supabase."
    ),
    version="1.0.0",
)

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to your frontend domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────────

class ExperimentConfig(BaseModel):
    """Explicit switches used by reproducible ablation and skill validation runs."""

    model_config = ConfigDict(extra="forbid")
    config_id: str = Field(default="custom", max_length=40)
    enable_reflexion: bool = True
    enable_memento: bool = True
    enable_skill_rules: bool = True
    enable_dual_critic: bool = True
    persist_run: bool = False
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    skill_rules_override: str | None = Field(default=None, max_length=20_000)


class GenerateRequest(BaseModel):
    prompt: str
    experiment: ExperimentConfig | None = None
    speed_mode: Literal["normal", "pro", "promax"] = "pro"
    skill_compression_mode: Literal["auto", "always", "off"] = "auto"
    skill_token_budget: int = Field(default=150, ge=40, le=600)
    available_context_tokens: int | None = Field(default=None, ge=100, le=32_768)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("prompt must not be empty")
        return v


class EvalScores(BaseModel):
    clip_score: float | None
    vlm_score: float | None
    visual_score: float | None
    pedagogical_score: float | None
    vlm_feedback: str | None


class GenerateResponse(BaseModel):
    image_base64: str | None           # PNG encoded as base64 string
    enhanced_prompt: str | None
    eval_scores: EvalScores
    db_record_id: str | None
    error: str | None                  # None = full success; non-None = partial/full failure
    retry_count: int
    config_id: str | None
    skill_compression: dict
    safety: dict


# ── Graph singleton — built once per container ────────────────────────────────

_graph = None

def _get_graph():
    global _graph
    if _graph is None:
        from orchestrator.graph import build_graph
        _graph = build_graph()
    return _graph


# ── Endpoints ─────────────────────────────────────────────────────────────────

@web_app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@web_app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Main pipeline endpoint.

    Runs: prompt-agent → image-agent → eval-agent → Supabase

    Returns the generated image (base64 PNG), the enhanced prompt,
    evaluation scores, and the Supabase record ID.

    Even on partial pipeline failure, returns whatever was successfully
    computed along with a descriptive error field — callers should check
    response.error before assuming all fields are populated.

    Expected latency: 30–120s depending on GPU cold-start state.
    """
    from shared.state import initial_state

    graph = _get_graph()
    experiment_config = req.experiment.model_dump() if req.experiment else {}
    state = initial_state(raw_prompt=req.prompt, experiment_config=experiment_config)
    state["speed_mode"] = req.speed_mode
    state["skill_compression_mode"] = req.skill_compression_mode
    state["skill_token_budget"] = req.skill_token_budget
    state["available_context_tokens"] = req.available_context_tokens

    try:
        final_state = graph.invoke(state)
    except Exception as exc:
        # Unrecoverable graph-level failure (rare — individual nodes catch errors)
        raise HTTPException(
            status_code=500,
            detail={"error": "PipelineError", "detail": str(exc)},
        )

    # Build the image_base64 field from bytes in state
    image_b64: str | None = None
    if final_state.get("image_bytes"):
        image_b64 = base64.b64encode(final_state["image_bytes"]).decode("utf-8")

    return GenerateResponse(
        image_base64=image_b64,
        enhanced_prompt=final_state.get("enhanced_prompt"),
        eval_scores=EvalScores(
            clip_score=final_state.get("clip_score"),
            vlm_score=final_state.get("vlm_score"),
            visual_score=final_state.get("visual_score"),
            pedagogical_score=final_state.get("pedagogical_score"),
            vlm_feedback=final_state.get("vlm_feedback"),
        ),
        db_record_id=final_state.get("db_record_id"),
        error=final_state.get("error"),
        retry_count=final_state.get("retry_count", 0),
        config_id=experiment_config.get("config_id") if experiment_config else None,
        skill_compression=final_state.get("skill_compression") or {},
        safety=final_state.get("safety") or {},
    )


# ── Global error handler — never expose raw tracebacks ───────────────────────

@web_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "InternalServerError", "detail": str(exc)},
    )


# ── Modal ASGI entrypoint ─────────────────────────────────────────────────────

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("agent-urls-secret"),
        modal.Secret.from_name("supabase-secret"),
    ],
    timeout=720,    # max pipeline time: 360s image + 150s eval + margin
)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
