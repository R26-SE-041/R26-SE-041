"""Validated vector sketches and deterministic ControlNet preprocessing."""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
CONTROL_MODEL = "xinsir/controlnet-scribble-sdxl-1.0"
DEFAULT_PROMPT = "A clean detailed illustration of the subject in the sketch, coherent shapes, natural colors, plain white background, no text, no watermark"
SIZE = 1024

Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]

class Stroke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: list[tuple[Coordinate, Coordinate]] = Field(min_length=1, max_length=5000)
    width: float = Field(default=0.006, ge=0.001, le=0.08, allow_inf_nan=False)
    tool: Literal["pen", "eraser"] = "pen"

class SketchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strokes: list[Stroke] = Field(min_length=1, max_length=500)
    instruction: str = Field(default="", max_length=2000)
    control_strength: float = Field(default=0.85, ge=0.3, le=1.3, allow_inf_nan=False)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def bounded_sketch(self):
        if sum(len(stroke.points) for stroke in self.strokes) > 30000:
            raise ValueError("Sketch is too complex; use at most 30,000 points")
        if not any(stroke.tool == "pen" for stroke in self.strokes):
            raise ValueError("Draw something before generating")
        return self

def render_sketch(strokes: list[Stroke], *, control: bool = False):
    from PIL import Image, ImageDraw, ImageOps
    canvas = Image.new("L", (SIZE, SIZE), 255)
    draw = ImageDraw.Draw(canvas)
    for stroke in strokes:
        points = [(round(x * (SIZE - 1)), round(y * (SIZE - 1))) for x, y in stroke.points]
        width = max(1, round(stroke.width * SIZE))
        color = 255 if stroke.tool == "eraser" else 0
        if len(points) > 1:
            draw.line(points, fill=color, width=width, joint="curve")
        radius = width / 2
        for x, y in (points[0], points[-1]):
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
    if canvas.getextrema()[0] == 255:
        raise ValueError("Sketch is blank; draw something before generating")
    # Scribble ControlNet expects light strokes on a dark background.
    return (ImageOps.invert(canvas) if control else canvas).convert("RGB")

def generation_prompt(instruction: str) -> str:
    return instruction.strip() or DEFAULT_PROMPT
