"""
agents/threed-agent/modal_app.py
──────────────────────────────────
2D → 3D Conversion Agent
  Model  : tencent/Hunyuan3D-2
  Pipeline:
    Stage 1 — Shape generation  : Hunyuan3DDiTFlowMatchingPipeline (~6 GB VRAM)
    Stage 2 — Texture synthesis  : Hunyuan3DPaintPipeline          (~16 GB total)
  GPUs:
    Normal / Pro  → A10G (24 GB VRAM — fits full pipeline with headroom)
    Pro Max       → H100 (80 GB VRAM — fastest inference, 2-3× speedup)

OUTPUT: base64-encoded .glb (textured 3D model, loadable by Three.js GLTFLoader)

FIRST-TIME SETUP (run once from backend/):
    modal run agents/threed-agent/modal_app.py::setup_model_weights

SERVE (dev):
    modal serve agents/threed-agent/modal_app.py

DEPLOY (prod):
    modal deploy agents/threed-agent/modal_app.py
"""

from __future__ import annotations

import base64
import io
import os
from typing import Optional

import modal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Constants ─────────────────────────────────────────────────────────────────

HUNYUAN_MODEL_ID  = "tencent/Hunyuan3D-2"
HUNYUAN_CACHE_PATH = "/model-cache/hunyuan3d-2"

# ── Volume (weights stored here — no re-download on cold start) ───────────────

threed_vol = modal.Volume.from_name("threed-weights-vol", create_if_missing=True)

# ── Container image ───────────────────────────────────────────────────────────

image = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install(
        "git", "ffmpeg", "libsm6", "libxext6",
        "libgl1-mesa-glx", "libglib2.0-0",   # OpenCV / OpenGL deps
        "build-essential", "ninja-build",     # needed to compile custom CUDA extensions
    )
    .pip_install(
        "torch>=2.4.0",
        "torchvision>=0.19.0",
        "huggingface_hub>=0.26.0",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "Pillow>=10.4.0",
        "numpy>=1.26.0",
        "trimesh>=4.5.0",
        "rembg>=2.0.57",    # background removal for cleaner 3D inputs
    )
    # Install hy3dgen from GitHub source (pip package alone lacks CUDA extensions)
    .run_commands(
        # Step 1: Install the Python package
        "pip install git+https://github.com/tencent/Hunyuan3D-2.git",
        # Step 2: Compile the custom CUDA rasterizer (needed for texture synthesis)
        "bash -c 'git clone https://github.com/tencent/Hunyuan3D-2.git /tmp/hunyuan3d "
        "&& cd /tmp/hunyuan3d/hy3dgen/texgen/custom_rasterizer "
        "&& python setup.py install || echo \"CUDA ext compile failed — shape-only mode\"'",
    )
)

app = modal.App("threed-agent", image=image)


# ── One-time setup: Download Hunyuan3D-2 weights into volume ─────────────────

@app.function(
    image=image,
    volumes={"/model-cache": threed_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=3600,
)
def setup_model_weights() -> None:
    """
    Download tencent/Hunyuan3D-2 weights into threed-weights-vol.
    Run ONCE from backend/:
        modal run agents/threed-agent/modal_app.py::setup_model_weights
    """
    from huggingface_hub import snapshot_download

    print(f"Downloading {HUNYUAN_MODEL_ID} → {HUNYUAN_CACHE_PATH} ...")
    snapshot_download(
        HUNYUAN_MODEL_ID,
        local_dir=HUNYUAN_CACHE_PATH,
        token=os.environ.get("HF_TOKEN"),
    )
    threed_vol.commit()
    print("Done. threed-weights-vol is ready.")


# ── Helper: Background removal ────────────────────────────────────────────────

def remove_background(image_bytes: bytes) -> bytes:
    """
    Strip the background and return RGBA PNG bytes.
    Hunyuan3D-2 produces cleaner shapes when the input is already
    background-free (white or transparent BG).
    """
    import rembg
    from PIL import Image as PILImage

    img = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
    result = rembg.remove(img)
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ── Base agent class (shared model loading logic) ─────────────────────────────

class _ThreeDAgentBase:
    """
    Shared implementation. GPU tier is set by the concrete subclass decorator.
    """

    @modal.enter()
    def load_pipelines(self) -> None:
        import torch
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        from hy3dgen.texgen import Hunyuan3DPaintPipeline
        from pathlib import Path

        # Set inside container so it doesn't affect Modal's import-time environment
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

        model_path = (
            HUNYUAN_CACHE_PATH
            if Path(HUNYUAN_CACHE_PATH).exists()
            and (Path(HUNYUAN_CACHE_PATH) / "config.json").exists()
            else HUNYUAN_MODEL_ID
        )

        print(f"Loading Hunyuan3D-2 shape pipeline from {model_path}…")
        self.shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
        )
        self.shape_pipe.to("cuda")

        print("Loading Hunyuan3D-2 texture pipeline…")
        self.tex_pipe = Hunyuan3DPaintPipeline.from_pretrained(model_path)
        print("Hunyuan3D-2 loaded successfully.")

    @modal.method()
    def convert(
        self,
        image_bytes: bytes,
        num_inference_steps: int = 50,
        texture: bool = True,
    ) -> dict:
        """
        Input : image_bytes (PNG/JPEG), inference steps, texture flag
        Output: { "glb_bytes": bytes, "error": str | None }
        """
        import torch
        from PIL import Image as PILImage

        try:
            torch.cuda.empty_cache()

            # Prepare image — ensure RGBA (BG removed upstream)
            pil_img = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")

            # Stage 1: Shape generation
            print("Stage 1 — generating 3D shape…")
            mesh = self.shape_pipe(
                image=pil_img,
                num_inference_steps=num_inference_steps,
            )[0]

            # Stage 2: Texture synthesis (optional but default)
            if texture:
                print("Stage 2 — synthesizing texture…")
                mesh = self.tex_pipe(mesh, image=pil_img)

            # Export to GLB bytes
            buf = io.BytesIO()
            mesh.export(buf, file_type="glb")
            buf.seek(0)
            glb_bytes = buf.read()

            print(f"GLB export complete — {len(glb_bytes) / 1024:.1f} KB")
            return {"glb_bytes": glb_bytes, "error": None}

        except Exception as exc:
            return {"glb_bytes": None, "error": f"Hunyuan3DFailed: {exc}"}


# ── A10G variant (Normal / Pro modes) ─────────────────────────────────────────

@app.cls(
    gpu="A10G",
    volumes={"/model-cache": threed_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=600,   # shape+texture can take up to 5 min on A10G
)
class ThreeDAgentA10G(_ThreeDAgentBase):
    """Hunyuan3D-2 on A10G (24 GB VRAM) — Normal and Pro modes."""


# ── H100 variant (Pro Max mode) ───────────────────────────────────────────────
# H100 (80 GB VRAM) gives 2-3× speedup over A10G for diffusion-based 3D generation.

@app.cls(
    gpu="H100",
    volumes={"/model-cache": threed_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=300,   # ~2-3× faster than A10G on H100
)
class ThreeDAgentH100(_ThreeDAgentBase):
    """Hunyuan3D-2 on H100 (80 GB VRAM) — Pro Max mode. Fastest 3D conversion."""


# ── FastAPI ───────────────────────────────────────────────────────────────────

web_app = FastAPI(
    title="3D Conversion Agent",
    description="Converts 2D images to textured 3D GLB models using Hunyuan3D-2",
    version="1.0.0",
)

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ConvertRequest(BaseModel):
    image_base64: str
    speed_mode: str = "pro"       # "normal" | "pro" | "promax"
    texture: bool = True          # False = shape-only (faster, no colour)
    num_inference_steps: int = 50  # 50 default; reduce to 30 for speed


@web_app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": HUNYUAN_MODEL_ID,
        "modes": {
            "normal": "A10G",
            "pro": "A10G",
            "promax": "H100",
        },
    }


@web_app.post("/convert")
def convert(req: ConvertRequest) -> dict:
    """
    Returns base64-encoded .glb bytes.
    Routes to H100 for Pro Max, A10G for Normal / Pro.
    """
    try:
        # 1. Decode image
        image_bytes = base64.b64decode(req.image_base64)

        # 2. Remove background for cleaner 3D reconstruction
        try:
            image_bytes = remove_background(image_bytes)
        except Exception:
            pass  # Skip bg removal on failure — still proceed

        # 3. Route to correct GPU tier
        if req.speed_mode == "promax":
            agent = ThreeDAgentH100()
        else:  # "normal" or "pro" → A10G
            agent = ThreeDAgentA10G()

        result = agent.convert.remote(
            image_bytes=image_bytes,
            num_inference_steps=req.num_inference_steps,
            texture=req.texture,
        )

        if result.get("error"):
            return {"glb_base64": None, "error": result["error"]}

        glb_bytes: bytes | None = result.get("glb_bytes")
        if not glb_bytes:
            return {"glb_base64": None, "error": "Empty GLB output"}

        return {
            "glb_base64": base64.b64encode(glb_bytes).decode("utf-8"),
            "size_kb": round(len(glb_bytes) / 1024, 1),
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as exc:
        return {"glb_base64": None, "error": f"ConversionFailed: {exc}"}


@app.function(image=image)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
