"""
agents/image-agent/modal_app.py
────────────────────────────────
Image Generation Agent
  Model  : black-forest-labs/FLUX.1-dev  (gated — HF token required)
  GPU    : A10G  (24 GB VRAM — bfloat16)
  Volume : model-weights-vol  → /model-cache/flux-dev

FIRST-TIME SETUP (run once from backend/):
    modal run agents/image-agent/modal_app.py::setup_model_weights

SERVE (dev):
    modal serve agents/image-agent/modal_app.py

DEPLOY (prod):
    modal deploy agents/image-agent/modal_app.py
"""

from __future__ import annotations

import base64
import io
import os
from typing import Any, Literal

import modal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Constants ─────────────────────────────────────────────────────────────────

FLUX_MODEL_ID   = "black-forest-labs/FLUX.1-dev"
FLUX_CACHE_PATH = "/model-cache/flux-dev"

IMAGE_HEIGHT         = 512
IMAGE_WIDTH          = 512
NUM_INFERENCE_STEPS  = 25   # 20-30 optimal for FLUX.1-dev flow matching
GUIDANCE_SCALE       = 3.5  # FLUX.1-dev recommended default

# ── Volume (weights stored here — no re-download on cold start) ───────────────

model_weights_vol = modal.Volume.from_name("model-weights-vol", create_if_missing=True)

# ── Container image ───────────────────────────────────────────────────────────

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "diffusers>=0.31.0",
        "transformers>=4.47.0",
        "torch>=2.4.0",
        "accelerate>=0.34.0",
        "huggingface_hub>=0.26.0",
        "safetensors>=0.4.5",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "Pillow>=10.4.0",
        "peft>=0.13.0",
    )
    .add_local_python_source("shared")
    .add_local_dir(
        "anatomy",
        remote_path="/root/anatomy",
        ignore=["**/__pycache__/**", "**/*.pyc"],
    )
)

app = modal.App("image-agent", image=image)

# Reduce CUDA memory fragmentation (helps on tight-VRAM GPUs like A10G with FLUX)
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"


# ── One-time setup: download FLUX.1-dev weights into the volume ───────────────

@app.function(
    image=image,
    volumes={"/model-cache": model_weights_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=3600,
)
def setup_model_weights() -> None:
    """
    Download FLUX.1-dev weights into model-weights-vol.
    Run ONCE from backend/:
        modal run agents/image-agent/modal_app.py::setup_model_weights
    """
    from huggingface_hub import snapshot_download

    print(f"Downloading {FLUX_MODEL_ID} → {FLUX_CACHE_PATH} ...")
    snapshot_download(
        FLUX_MODEL_ID,
        local_dir=FLUX_CACHE_PATH,
        token=os.environ.get("HF_TOKEN"),
    )
    model_weights_vol.commit()
    print("Done. model-weights-vol is ready.")


# ── Agent class ───────────────────────────────────────────────────────────────

class _ImageAgentBase:
    """FLUX.1-dev image generation on A10G. Pipeline loaded once per container."""

    @modal.enter()
    def load_pipeline(self) -> None:
        import torch
        from diffusers import FluxPipeline

        self.pipe = FluxPipeline.from_pretrained(
            FLUX_CACHE_PATH,
            torch_dtype=torch.bfloat16,
        )
        # Optimize based on GPU
        if getattr(self, "USE_SEQUENTIAL_OFFLOAD", False):
            # Sequential offload: only ONE pipeline component lives in VRAM at a time.
            # Slower than model_cpu_offload but fits FLUX.1-dev on A10G (22 GB).
            self.pipe.enable_sequential_cpu_offload()
        else:
            # A100 and H100 have 40GB/80GB VRAM, enough to hold the model fully in memory.
            self.pipe.to("cuda")

    @modal.method()
    def generate(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Generate an image from a prompt.

        Input:  {"prompt": str}
        Output: {"image_bytes": bytes, "error": str | None}
        """
        prompt = (state_dict.get("prompt") or "").strip()
        if not prompt:
            return {"image_bytes": None, "error": "prompt is empty"}

        from shared.safety import assess_prompt, blocked_error
        safety = assess_prompt(prompt)
        if not safety.allowed:
            return {
                "image_bytes": None,
                "safety": safety.to_dict(),
                "error": blocked_error(safety),
            }

        try:
            import torch
            torch.cuda.empty_cache()  # free any fragmented allocations before inference
            seed = state_dict.get("seed")
            generator = None
            if seed is not None:
                generator = torch.Generator(device="cuda").manual_seed(int(seed))
            result = self.pipe(
                prompt=prompt,
                height=IMAGE_HEIGHT,
                width=IMAGE_WIDTH,
                num_inference_steps=NUM_INFERENCE_STEPS,
                guidance_scale=GUIDANCE_SCALE,
                generator=generator,
            )
            buf = io.BytesIO()
            result.images[0].save(buf, format="PNG")
            buf.seek(0)
            return {"image_bytes": buf.read(), "safety": safety.to_dict(), "error": None}

        except Exception as exc:
            return {"image_bytes": None, "error": f"ImageGenerationFailed: {exc}"}


# ── H100 variant (Pro Max mode) ──────────────────────────────────────────────────
# H100 (Hopper) is 1.5–2× faster than A100 for FLUX.1-dev diffusion inference.
# It replaces A100 for Pro Max to maximise generation speed.

@app.cls(
    gpu="A10G",
    secrets=[modal.Secret.from_name("hf-secret")],
    volumes={"/model-cache": model_weights_vol},
    timeout=600,
    scaledown_window=300,
)
class ImageAgentA10G(_ImageAgentBase):
    """FLUX.1-dev image generation on A10G. Pipeline loaded once per container."""
    USE_SEQUENTIAL_OFFLOAD = True

@app.cls(
    gpu="A100",
    secrets=[modal.Secret.from_name("hf-secret")],
    volumes={"/model-cache": model_weights_vol},
    timeout=300,
    scaledown_window=300,
)
class ImageAgentA100(_ImageAgentBase):
    """FLUX.1-dev on A100 — (Pro mode)."""

@app.cls(
    gpu="H100",
    secrets=[modal.Secret.from_name("hf-secret")],
    volumes={"/model-cache": model_weights_vol},
    timeout=180,
    scaledown_window=300,
)
class ImageAgentH100(_ImageAgentBase):
    """FLUX.1-dev on H100 — fastest available inference (Pro Max mode)."""


# ── FastAPI ───────────────────────────────────────────────────────────────

web_app = FastAPI(
    title="Image Generation Agent",
    description="Generates images using FLUX.1-dev on A10G GPU",
    version="1.0.0",
)

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class EnhancedPromptPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    final_prompt: str = Field(min_length=1, max_length=30_000)
    anatomy_spec: dict[str, Any] = Field(default_factory=lambda: {"is_anatomy": False})


class GenerateRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=30_000)
    enhanced_prompt_json: EnhancedPromptPayload | None = None
    speed_mode: Literal["normal", "pro", "promax"] = "pro"
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    regeneration_feedback: str | None = Field(default=None, max_length=2000)
    memory_context: str | None = Field(default=None, max_length=2000)
    domain: Literal["generic", "anatomy"] = "generic"
    organ: str | None = Field(default=None, max_length=80)
    view: str | None = Field(default=None, max_length=80)
    use_skill_rules: bool = True


@web_app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": FLUX_MODEL_ID,
        "variants": ["base"],
        "prompt_policies": ["generic-preserve-intent-v1", "anatomy-clean-base-v1"],
    }


@web_app.post("/generate")
def generate(req: GenerateRequest) -> dict:
    """Returns base64-encoded PNG. Routes to A10G (Normal/Pro) or A100 (Pro Max)."""
    try:
        # CPU-side preflight avoids allocating an expensive GPU container for a
        # prompt that the generation method will reject again.
        from shared.safety import assess_prompt, blocked_error
        enhanced_payload = req.enhanced_prompt_json
        if enhanced_payload:
            generation_prompt = enhanced_payload.final_prompt.strip()
            anatomy_spec = enhanced_payload.anatomy_spec
        else:
            generation_prompt = (req.prompt or "").strip()
            anatomy_spec = {"is_anatomy": req.domain == "anatomy"}
        if not generation_prompt:
            raise HTTPException(status_code=422, detail={"error": "PromptRequired"})

        domain = "anatomy" if anatomy_spec.get("is_anatomy") else req.domain
        organ = anatomy_spec.get("organ") or req.organ
        view = anatomy_spec.get("view") or req.view
        if enhanced_payload and domain == "anatomy":
            from anatomy import compile_any_anatomy_prompt

            validated_spec, canonical_prompt = compile_any_anatomy_prompt(anatomy_spec)
            if generation_prompt != canonical_prompt:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "EnhancedPromptSpecMismatch"},
                )
            generation_prompt = canonical_prompt
            organ = validated_spec["organ"]
            view = validated_spec.get("view") or validated_spec.get("view_description") or req.view

        feedback = (req.regeneration_feedback or "").strip()
        safety = assess_prompt("\n".join(filter(None, [generation_prompt, feedback])))
        if not safety.allowed:
            return {
                "image_base64": None,
                "safety": safety.to_dict(),
                "error": blocked_error(safety),
            }
        # Pro Max gets H100 for fastest FLUX.1-dev inference
        if req.speed_mode == "promax":
            agent = ImageAgentH100()
        elif req.speed_mode == "pro":
            agent = ImageAgentA100()
        else:  # "normal" → A10G (same as original)
            agent = ImageAgentA10G()
        from shared.image_policies import select_image_policy

        policy = select_image_policy(domain)
        generation_prompt = policy.apply(
            generation_prompt,
            memory_context=req.memory_context or "",
            feedback=feedback,
        )
        result = agent.generate.remote({"prompt": generation_prompt, "seed": req.seed})

        if result.get("error"):
            return {
                "image_base64": None,
                "safety": result.get("safety"),
                "error": result["error"],
            }

        image_bytes: bytes | None = result.get("image_bytes")
        if not image_bytes:
            return {"image_base64": None, "error": "Empty image output"}

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "image_base64": encoded,
            "base_image_base64": encoded,
            "model_variant": "base",
            "generation_metadata": {
                "domain": domain,
                "policy_id": policy.policy_id,
                "organ": organ,
                "view": view,
                "seed": req.seed,
                "input_contract": "enhanced_prompt_json" if enhanced_payload else "direct_prompt",
                "anatomy_output_rules_applied": domain == "anatomy",
            },
            "safety": result.get("safety"),
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as exc:
        return {"image_base64": None, "error": f"ImageGenerationFailed: {exc}"}


@app.function(image=image, timeout=900)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
