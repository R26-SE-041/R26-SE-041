"""Validated public contracts. Owners and service URLs are never client supplied."""
from __future__ import annotations
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from shared.sketch import SketchRequest

class Annotation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    structure_id: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=80)
    anchor_x: float = Field(ge=0, le=1, allow_inf_nan=False)
    anchor_y: float = Field(ge=0, le=1, allow_inf_nan=False)
    label_x: float = Field(ge=0, le=1, allow_inf_nan=False)
    label_y: float = Field(ge=0, le=1, allow_inf_nan=False)
    confidence: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    verified: bool = False
    user_edited: bool = False
    source: Literal["automatic", "manual"] = "automatic"

class ImageSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["point", "box"]
    coords: list[float] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def validate_coords(self):
        import math
        if len(self.coords) != (2 if self.type == "point" else 4):
            raise ValueError("Invalid selection coordinates")
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in self.coords):
            raise ValueError("Selection must use normalized coordinates")
        if self.type == "box" and (self.coords[0] >= self.coords[2] or self.coords[1] >= self.coords[3]):
            raise ValueError("Selection box must have positive area")
        return self

class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    mode: Literal["identify", "explain", "ask"]
    question: str = Field(default="", max_length=4000)
    interaction: ImageSelection
    organ: str | None = Field(default=None, max_length=80)
    structure_id: str | None = Field(default=None, max_length=160)
    regeneration_feedback: str | None = Field(default=None, max_length=2000)
    memory_context: str = Field(default="", max_length=16000)

    @model_validator(mode="after")
    def validate_question(self):
        if self.mode == "ask" and not self.question.strip():
            raise ValueError("Question is required")
        return self

class EnhancementContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retry_feedback: str | None = Field(default=None, max_length=2000)
    anatomy_memory: str = Field(default="", max_length=16000)
    generic_memory: str = Field(default="", max_length=16000)

class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    kind: Literal["generate", "sketch", "labels", "threed", "analysis", "enhance"]
    generation_id: UUID | None = None
    mode: Literal["general", "anatomy", "sketch"] = "general"
    prompt: str = Field(default="", max_length=30000)
    raw_prompt: str = Field(default="", max_length=4000)
    feedback: str = Field(default="", max_length=2000)
    speed_mode: Literal["normal", "pro", "promax"] = "pro"
    sketch: SketchRequest | None = None
    analysis: AnalysisRequest | None = None
    enhancement_context: EnhancementContext = Field(default_factory=EnhancementContext)
    prompt_event_id: str | None = Field(default=None, max_length=160)
    anatomy: dict = Field(default_factory=lambda: {"is_anatomy": False})
    enhanced_payload: dict | None = None
    chat_id: str | None = Field(default=None, max_length=128)
    auto_label: bool = True

    @model_validator(mode="after")
    def validate_kind(self):
        if self.kind == "sketch" and self.sketch is None:
            raise ValueError("Sketch data is required")
        if self.kind in {"generate", "enhance"} and not self.prompt.strip():
            raise ValueError("Prompt is required")
        if self.kind in {"labels", "threed", "analysis"} and self.generation_id is None:
            raise ValueError("Source generation is required")
        if self.kind == "analysis" and self.analysis is None:
            raise ValueError("Analysis request is required")
        if len(str(self.anatomy)) > 16000 or len(str(self.enhanced_payload or {})) > 40000:
            raise ValueError("Anatomy context is too large")
        if self.kind == "sketch":
            from shared.sketch import render_sketch
            render_sketch(self.sketch.strokes)  # Reject blank/erased sketches before queueing.
        return self

class HistoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    anatomyAnnotations: list[Annotation] | None = Field(default=None, max_length=64)
    interactions: list[dict] | None = Field(default=None, max_length=500)

class Interaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    createdAt: str = Field(max_length=80)
    mode: Literal["identify", "explain", "ask"]
    question: str | None = Field(default=None, max_length=4000)
    answer: str = Field(max_length=20000)
    selection: ImageSelection | None = None
    structureId: str | None = Field(default=None, max_length=160)
    status: Literal["queued", "completed", "failed"] = "completed"
    error: str | None = Field(default=None, max_length=500)

class ChatEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=160)
    kind: Literal["prompt", "enhancement"]
    data: dict

    @model_validator(mode="after")
    def bound_data(self):
        import json
        if len(json.dumps(self.data)) > 80000:
            raise ValueError("Conversation event is too large")
        return self

class ChatPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=80)

class HistoryImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    legacy_id: str = Field(min_length=1, max_length=160)
    created_at: str = Field(max_length=80)
    metadata: dict
    image_base64: str = Field(min_length=1, max_length=40_000_000)
    glb_base64: str | None = Field(default=None, max_length=140_000_000)

    @model_validator(mode="after")
    def validate_metadata(self):
        from datetime import datetime
        datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        if len(str(self.metadata)) > 200_000:
            raise ValueError("History metadata is too large")
        if self.metadata.get("mode") not in {"general","anatomy","sketch"}:
            raise ValueError("Unknown generation mode")
        for item in self.metadata.get("anatomyAnnotations", []):
            Annotation.model_validate(item)
        return self
