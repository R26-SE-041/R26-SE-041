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
      DATABASE_URL=postgresql://user:password@host:5432/dbname \
      SUPABASE_URL=https://<project-ref>.supabase.co \
      SUPABASE_ANON_KEY=<publishable-anon-key>

DEPLOY (from backend/ directory):
    cd backend
    modal deploy orchestrator/modal_app.py

REST CONTRACT: see README.md
"""

from __future__ import annotations

import base64
import json
import os
from typing import Literal
from uuid import UUID

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
    prompt_model_variant: Literal["base", "anatomy_lora"] = "base"
    # FLUX.1-dev is intentionally the only image-generation pipeline.
    image_model_variant: Literal["base"] = "base"
    interactive_model_variant: Literal["base"] = "base"
    enable_anatomy_critic: bool = True


class GenerateRequest(BaseModel):
    prompt: str
    experiment: ExperimentConfig | None = None
    speed_mode: Literal["normal", "pro", "promax"] = "pro"

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
    anatomy_metrics: dict = Field(default_factory=dict)
    anatomy_hard_failures: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    image_base64: str | None           # PNG encoded as base64 string
    enhanced_prompt: str | None
    eval_scores: EvalScores
    db_record_id: str | None
    error: str | None                  # None = full success; non-None = partial/full failure
    retry_count: int
    config_id: str | None
    safety: dict
    anatomy_spec: dict = Field(default_factory=lambda: {"is_anatomy": False})
    routing: dict = Field(default_factory=dict)
    model_variants: dict[str, str] = Field(default_factory=dict)


FeedbackAgent = Literal[
    "prompt-agent", "prompt-anatomy", "prompt-generic",
    "image-agent", "interactive-agent", "eval-agent", "threed-agent"
]

FEEDBACK_REASON_CODES: dict[str, set[str]] = {
    "prompt-agent": {"meaning_changed", "not_visual", "too_verbose", "factually_incorrect", "wrong_level", "clear", "accurate", "well_structured"},
    "prompt-anatomy": {
        "wrong_view", "missing_structure", "extra_structure", "labels_requested",
        "background_not_white", "inaccurate_anatomy", "wrong_detail_level",
        "view_preserved", "structures_preserved", "concise", "accurate",
    },
    "prompt-generic": {
        "subject_changed", "wrong_style", "poor_composition", "missing_detail", "too_verbose",
        "subject_preserved", "good_style", "good_composition", "concise",
    },
    "image-agent": {"bad_labels", "poor_layout", "wrong_content", "wrong_style", "inaccurate_diagram", "clear_labels", "good_layout", "accurate", "matches_request"},
    "interactive-agent": {"wrong_region", "incorrect_explanation", "too_complex", "not_useful", "grounded", "clear", "helpful"},
    "eval-agent": {"wrong_score", "missed_error", "unhelpful_feedback", "well_calibrated", "actionable"},
    "threed-agent": {"bad_geometry", "bad_texture", "wrong_subject", "good_geometry", "good_texture", "matches_source"},
}


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=128)
    pipeline_run_id: str | None = None
    agent_name: FeedbackAgent
    output_id: str = Field(min_length=1, max_length=128)
    parent_feedback_id: str | None = None
    parent_output_id: str | None = Field(default=None, max_length=128)
    rating: Literal[-1, 1]
    reason_codes: list[str] = Field(default_factory=list, max_length=8)
    comment: str | None = Field(default=None, max_length=2000)
    input_context: dict = Field(default_factory=dict)
    output_snapshot: dict = Field(default_factory=dict)
    model_version: str | None = Field(default=None, max_length=120)
    skill_version: str | None = Field(default=None, max_length=120)

    @field_validator("reason_codes")
    @classmethod
    def normalize_reason_codes(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})


class MemoryContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_name: FeedbackAgent
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=10)


class MemorySettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_enabled: bool


def _authenticated_user_id(request: Request) -> str | None:
    """Resolve a Supabase user from a bearer token; never trust a body user_id."""
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
    if not supabase_url or not anon_key:
        raise HTTPException(status_code=503, detail={"error": "SupabaseAuthNotConfigured"})
    try:
        import requests
        response = requests.get(
            f"{supabase_url}/auth/v1/user",
            headers={"apikey": anon_key, "Authorization": f"Bearer {token}"},
            timeout=8,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail={"error": "SupabaseAuthUnavailable"})
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail={"error": "InvalidAccessToken"})
    subject = str((response.json() or {}).get("id") or "")
    try:
        return str(UUID(subject))
    except ValueError:
        raise HTTPException(status_code=401, detail={"error": "InvalidAccessTokenSubject"})


def _require_user_id(request: Request) -> str:
    user_id = _authenticated_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail={"error": "AuthenticationRequired"})
    return user_id


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
            anatomy_metrics=final_state.get("anatomy_metrics") or {},
            anatomy_hard_failures=final_state.get("anatomy_hard_failures") or [],
        ),
        db_record_id=final_state.get("db_record_id"),
        error=final_state.get("error"),
        retry_count=final_state.get("retry_count", 0),
        config_id=experiment_config.get("config_id") if experiment_config else None,
        safety=final_state.get("safety") or {},
        anatomy_spec=final_state.get("anatomy_spec") or {"is_anatomy": False},
        routing=final_state.get("routing") or {},
        model_variants=final_state.get("model_variants") or {},
    )


@web_app.post("/feedback", status_code=201)
def feedback(req: FeedbackRequest, request: Request) -> dict:
    """Store a stage-specific rating and link corrected liked retries as pairs."""
    allowed_reasons = FEEDBACK_REASON_CODES[req.agent_name]
    invalid = sorted(set(req.reason_codes) - allowed_reasons)
    if invalid:
        raise HTTPException(status_code=422, detail={"error": "InvalidReasonCodes", "codes": invalid})
    if req.rating == -1 and not req.reason_codes and not (req.comment or "").strip():
        raise HTTPException(status_code=422, detail={"error": "DislikeReasonRequired"})
    if req.parent_feedback_id and req.rating != 1:
        raise HTTPException(status_code=422, detail={"error": "Only a liked retry can complete a preference pair"})
    if len(json.dumps(req.input_context, default=str)) > 10_000:
        raise HTTPException(status_code=413, detail={"error": "InputContextTooLarge"})
    if len(json.dumps(req.output_snapshot, default=str)) > 20_000:
        raise HTTPException(status_code=413, detail={"error": "OutputSnapshotTooLarge"})
    try:
        from shared.db import record_agent_feedback
        result = record_agent_feedback(
            **req.model_dump(),
            auth_user_id=_authenticated_user_id(request),
        )
        learning: dict = {}
        if result.get("preference_pair_id"):
            try:
                from shared.feedback_learning import enrich_preference_pair
                learning = enrich_preference_pair(str(result["preference_pair_id"]))
            except Exception:
                # The durable pair is retained for the scheduled backfill job.
                learning = {"embedded": False, "deferred": True}
        return {**result, "status": "recorded", "learning": learning}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    except Exception:
        raise HTTPException(status_code=503, detail={"error": "FeedbackPersistenceFailed"})


@web_app.post("/memory/context")
def memory_context(req: MemoryContextRequest, request: Request) -> dict:
    """Return token-ready deployed memories with strict user and agent scoping."""
    try:
        from shared.memory import MemoryManager
        memories = MemoryManager(agent_name=req.agent_name).recall_scoped(
            query=req.query,
            user_id=_authenticated_user_id(request),
            limit=req.limit,
        )
        return {
            "agent_name": req.agent_name,
            "memories": memories,
            "context": "\n".join(f"- {item['content']}" for item in memories),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail={"error": "MemoryRetrievalFailed"})


@web_app.get("/memory/settings")
def memory_settings(request: Request) -> dict:
    from shared.db import get_user_memory_settings
    return get_user_memory_settings(_require_user_id(request))


@web_app.post("/memory/settings")
def update_memory_settings(req: MemorySettingsRequest, request: Request) -> dict:
    from shared.db import set_user_memory_enabled
    return set_user_memory_enabled(_require_user_id(request), req.memory_enabled)


@web_app.get("/memory/preferences")
def memory_preferences(request: Request) -> dict:
    from shared.db import list_user_preferences
    return {"preferences": list_user_preferences(_require_user_id(request))}


@web_app.post("/memory/preferences/{preference_id}/revoke")
def revoke_memory_preference(preference_id: UUID, request: Request) -> dict:
    from shared.db import revoke_user_preference
    if not revoke_user_preference(_require_user_id(request), str(preference_id)):
        raise HTTPException(status_code=404, detail={"error": "PreferenceNotFound"})
    return {"status": "revoked", "preference_id": str(preference_id)}


@web_app.post("/memory/clear")
def clear_memory(request: Request) -> dict:
    from shared.db import clear_user_preferences
    return {"status": "cleared", "deleted": clear_user_preferences(_require_user_id(request))}


# ── Global error handler — never expose raw tracebacks ───────────────────────

@web_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "InternalServerError"},
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
