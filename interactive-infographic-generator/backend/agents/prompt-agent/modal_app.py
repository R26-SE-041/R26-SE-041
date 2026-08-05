"""
agents/prompt-agent/modal_app.py
─────────────────────────────────
Prompt Enhancement Agent
  Model : Qwen/Qwen2.5-3B-Instruct  ← exact string, do NOT substitute
  GPU   : T4  (6 GB VRAM — adequate for a 3B model at fp16)
  Rules : loaded from skills/SKILL.md via Modal Volume (skills-vol)

COLD-START STRATEGY:
  - Model weights are baked into the container image during `modal deploy`
    via image.run_function(_download_model). They are NOT re-downloaded
    on every cold start.
  - SKILL.md is read from a mounted Volume at /root/skills/SKILL.md.
    Update the Volume contents without rebuilding the image.

DEPLOY (from backend/ directory):
    cd backend
    modal deploy agents/prompt-agent/modal_app.py

HEALTH CHECK:
    GET <deployed-url>/health
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import modal

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"   # ← do NOT change; 7B would OOM on T4
MODEL_CACHE = "/root/models/qwen3b"
SKILL_PATH = "/root/skills/SKILL.md"
MAX_JSON_RETRIES = 2


# ── Image build: download model weights once, bake into image layer ───────────

def _download_model() -> None:
    """Runs during `modal deploy` (image build), not at request time."""
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL_ID, local_dir=MODEL_CACHE)


skills_vol = modal.Volume.from_name("skills-vol", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers>=4.47.0",
        "torch>=2.4.0",
        "accelerate>=0.34.0",
        "huggingface_hub>=0.26.0",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "typing_extensions>=4.12.0",
    )
    # Bake model weights into the image (runs once on deploy, not on cold start)
    .run_function(
        _download_model,
        secrets=[modal.Secret.from_name("hf-secret")],
    )
    # Add shared/ package — run `modal deploy` from backend/ so this path resolves
    .add_local_python_source("shared")
)

app = modal.App("prompt-agent", image=image)


# ── Agent class (GPU-bound, one container load per lifetime) ──────────────────

class _PromptAgentBase:
    """
    Qwen2.5-3B-Instruct prompt enhancement agent.
    Model is loaded once per container in @modal.enter(); subsequent
    requests reuse the warm model in VRAM.
    """

    @modal.enter()
    def load_model(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_CACHE,
            trust_remote_code=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_CACHE,
            torch_dtype=torch.float16,
            device_map="cuda",
            trust_remote_code=True,
        )
        self.model.eval()

        # Load SKILL.md once at container start; re-read if the Volume is updated
        # by re-deploying (or do a rolling restart via `modal app restart prompt-agent`).
        skill_file = Path(SKILL_PATH)
        self.skill_rules: str = (
            skill_file.read_text(encoding="utf-8")
            if skill_file.exists()
            else "# No rules loaded — upload SKILL.md to the skills-vol Volume"
        )

    # ── Private inference helper ──────────────────────────────────────────────

    def _infer(self, prompt: str) -> str:
        """Single LLM inference call. Returns raw text output."""
        import torch

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer([text], return_tensors="pt").to("cuda")

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.3,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # Decode only newly generated tokens (not the prompt echo)
        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    # ── Public Modal method ───────────────────────────────────────────────────

    @modal.method()
    def enhance(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Enhance a raw image generation prompt.

        Input:  {"raw_prompt": str}
        Output: {"enhanced_prompt": str | None,
                 "prompt_parse_error": bool,
                 "error": str | None}

        Contract:
          - If raw_prompt is empty → returns error, no LLM call made.
          - If JSON parsing fails after MAX_JSON_RETRIES → returns raw text
            as enhanced_prompt with prompt_parse_error=True. Pipeline continues.
          - Never raises; all failures are captured in the returned dict.
        """
        from shared.json_utils import parse_json_with_retry

        raw_prompt = (state_dict.get("raw_prompt") or "").strip()
        if not raw_prompt:
            return {
                "enhanced_prompt": None,
                "prompt_parse_error": False,
                "error": "raw_prompt is empty or missing",
            }

        system_prompt = (
            "You are an expert educational image prompt engineer.\n\n"
            f"Enhancement Rules:\n{self.skill_rules}\n\n"
            "Given the raw prompt below, produce an enhanced version that is:\n"
            "  1. Grammatically correct\n"
            "  2. Visually descriptive (style, composition, lighting)\n"
            "  3. Educationally appropriate for the subject matter\n\n"
            'Respond with ONLY a JSON object: {"enhanced_prompt": "<your enhanced prompt>"}\n'
            "No prose. No markdown. No code fences.\n\n"
            f"Raw prompt: {raw_prompt}"
        )

        raw_output = self._infer(system_prompt)

        parsed, had_error = parse_json_with_retry(
            raw_output=raw_output,
            llm_fn=self._infer,
            correction_prompt=(
                f"Enhance this educational image generation prompt: {raw_prompt}"
            ),
            max_retries=MAX_JSON_RETRIES,
        )

        if had_error or parsed is None:
            # Graceful fallback: use raw LLM text rather than killing the pipeline
            return {
                "enhanced_prompt": raw_output.strip() or raw_prompt,
                "prompt_parse_error": True,
                "error": None,
            }

        enhanced = (parsed.get("enhanced_prompt") or "").strip()
        if not enhanced:
            # Guard: LLM returned valid JSON but with an empty/missing key
            enhanced = raw_prompt

        return {
            "enhanced_prompt": enhanced,
            "prompt_parse_error": False,
            "error": None,
        }


# ── A10G variant (Pro / Pro Max modes) ───────────────────────────────────────

@app.cls(
    gpu="T4",
    secrets=[modal.Secret.from_name("hf-secret")],
    volumes={"/root/skills": skills_vol},
    timeout=120,
)
class PromptAgentT4(_PromptAgentBase):
    """Qwen2.5-3B-Instruct on T4 (Normal mode)."""

@app.cls(
    gpu="A10G",
    secrets=[modal.Secret.from_name("hf-secret")],
    volumes={"/root/skills": skills_vol},
    timeout=60,
)
class PromptAgentA10G(_PromptAgentBase):
    """Same model as PromptAgentT4 but on A10G for faster inference (Pro / Pro Max modes)."""


# ── FastAPI web app (CPU-only ASGI endpoint, calls GPU class remotely) ────────

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

web_app = FastAPI(
    title="Prompt Enhancement Agent",
    description="Enhances image generation prompts using Qwen2.5-3B-Instruct",
    version="1.0.0",
)

# Allow browser calls from any origin (frontend on localhost:3000 or deployed)
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class EnhanceRequest(BaseModel):
    raw_prompt: str
    speed_mode: str = "pro"  # "normal" | "pro" | "promax"


@web_app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_ID}


@web_app.post("/enhance")
def enhance(req: EnhanceRequest) -> dict:
    try:
        # Route to the correct GPU tier based on speed_mode
        if req.speed_mode == "normal":
            agent = PromptAgentT4()
        else:  # "pro" or "promax" → A10G
            agent = PromptAgentA10G()
        result = agent.enhance.remote({"raw_prompt": req.raw_prompt})
        return result
    except Exception as exc:
        # Never expose raw stack traces to callers
        raise HTTPException(
            status_code=500,
            detail={"error": "PromptEnhancementFailed", "detail": str(exc)},
        )


@app.function(image=image)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
