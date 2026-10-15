"""
agents/threed-agent/modal_app.py
──────────────────────────────────
2D → 3D Conversion Agent
  Model  : tencent/Hunyuan3D-2
  Pipeline:
    Stage 1 — Shape generation  : Hunyuan3DDiTFlowMatchingPipeline (~6 GB VRAM)
    Stage 2 — Texture synthesis  : Hunyuan3DPaintPipeline          (~16 GB total)
  GPUs:
    Normal        → A10G (24 GB VRAM)
    Pro           → A100 (40 GB VRAM)
    Pro Max       → H100 (80 GB VRAM)

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
import time
import traceback
from contextlib import contextmanager
from functools import lru_cache
from typing import Literal

import modal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Constants ─────────────────────────────────────────────────────────────────

HUNYUAN_MODEL_ID  = "tencent/Hunyuan3D-2"
HUNYUAN_CACHE_PATH = "/model-cache/hunyuan3d-2"
# Install the Python package and both native extensions from the same source.
HUNYUAN_REVISION = "f8db63096c8282cb27354314d896feba5ba6ff8a"
MAX_TEXTURE_FACES = 40_000  # upstream Gradio app's FaceReducer default
TEXTURE_RESOLUTION = 1024
GPU_TIMEOUT_SECONDS = 3600

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
        "torch==2.4.1",
        "torchvision==0.19.1",
        # Hunyuan 2.0.2 requires transformers>=4.48.  Keep it below the newer
        # releases that import torch.distributed.tensor.DTensor, which is not
        # exported by our pinned torch 2.4.1 and crashes every GPU container.
        "transformers==4.48.3",
        "diffusers==0.30.0",
        "accelerate==1.1.1",
        "setuptools",
        "wheel",
        "huggingface_hub>=0.26.0",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "Pillow>=10.4.0",
        "numpy>=1.26.0",
        "trimesh>=4.5.0",
        "rembg>=2.0.57",    # background removal for cleaner 3D inputs
    )
    # Modal builds images without a visible GPU, so torch cannot infer which
    # CUDA architectures to compile.  Cover all three deployment GPU tiers.
    .env({
        "TORCH_CUDA_ARCH_LIST": "8.0;8.6;9.0",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        "HF_HOME": "/model-cache/huggingface",
        "U2NET_HOME": "/model-cache/rembg",
    })
    # Install hy3dgen from GitHub source (pip package alone lacks CUDA extensions)
    .run_commands(
        # Step 1: Install the Python package
        f"pip install git+https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git@{HUNYUAN_REVISION}",
        # Step 2: Compile the custom CUDA rasterizer (needed for texture synthesis)
        "bash -c 'git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git /tmp/hunyuan3d "
        f"&& cd /tmp/hunyuan3d && git checkout {HUNYUAN_REVISION} "
        "&& cd hy3dgen/texgen/custom_rasterizer "
        "&& CC=gcc CXX=g++ pip install --no-build-isolation .'",
    )
    # Upstream's paint pipeline also requires this second native extension.
    .run_commands(
        "bash -c 'cd /tmp/hunyuan3d/hy3dgen/texgen/differentiable_renderer "
        "&& CC=gcc CXX=g++ pip install --no-build-isolation .'",
        # Fail the image build if either paint extension is unavailable. A
        # textured request must never degrade silently to an untextured mesh.
        # Loading torch first makes its shared libraries (including libc10.so)
        # available to the native rasterizer, matching Hunyuan's runtime order.
        "python -c \"import torch; import custom_rasterizer; import mesh_processor\"",
    )
    # PyMeshLab's texture/mesh plugins dynamically load libOpenGL.so.0.
    .apt_install("libopengl0")
)

app = modal.App("threed-agent", image=image)
conversion_jobs = modal.Dict.from_name("threed-conversion-jobs", create_if_missing=True)
conversion_progress = modal.Dict.from_name("threed-conversion-progress", create_if_missing=True)


@contextmanager
def conversion_stage(call_id: str | None, stage: str):
    """Expose real stage boundaries without letting telemetry break inference."""
    started = time.monotonic()
    print(f"3D stage: {stage}", flush=True)
    if call_id:
        try:
            conversion_progress[call_id] = {"stage": stage}
        except Exception as exc:
            print(f"Could not publish 3D progress: {exc}", flush=True)
    yield
    print(f"3D stage complete: {stage} ({time.monotonic() - started:.1f}s)", flush=True)


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

@lru_cache(maxsize=1)
def background_session():
    import rembg

    # Avoid a changing rembg default downloading a >1 GB model or creating an
    # ONNX session on every request. Mesh work and diffusion retain the GPU.
    return rembg.new_session("u2net", providers=["CPUExecutionProvider"])


def remove_background(image_bytes: bytes) -> bytes:
    """
    Strip the background and return RGBA PNG bytes.
    Hunyuan3D-2 produces cleaner shapes when the input is already
    background-free (white or transparent BG).
    """
    import rembg
    from PIL import Image as PILImage

    img = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
    # Already transparent images do not need another segmentation pass.
    if img.getextrema()[3][0] < 255:
        return image_bytes
    result = rembg.remove(img, session=background_session())
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

        model_path = (
            HUNYUAN_CACHE_PATH
            if Path(HUNYUAN_CACHE_PATH).exists()
            and (Path(HUNYUAN_CACHE_PATH) / "config.json").exists()
            else HUNYUAN_MODEL_ID
        )

        print(f"Loading Hunyuan3D-2 shape pipeline from {model_path}…")
        self.shape_pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            model_path,
            dtype=torch.float16,
        )
        self.shape_pipe.to("cuda")

        print("Loading Hunyuan3D-2 texture pipeline…")
        # Pin the paint variant too: an upstream default change must not silently
        # switch the scheduler/model on the next image build.
        self.tex_pipe = Hunyuan3DPaintPipeline.from_pretrained(
            model_path, subfolder="hunyuan3d-paint-v2-0-turbo",
        )
        self.tex_pipe.config.render_size = TEXTURE_RESOLUTION
        self.tex_pipe.config.texture_size = TEXTURE_RESOLUTION
        self.tex_pipe.render.set_default_render_resolution(TEXTURE_RESOLUTION)
        self.tex_pipe.render.set_default_texture_resolution(TEXTURE_RESOLUTION)
        # The renderer computes this kernel at construction, before resizing.
        self.tex_pipe.render.bake_unreliable_kernel_size = int(2 / 512 * TEXTURE_RESOLUTION)
        # Upstream disables these bars; retain visibility while diffusion runs.
        for model in self.tex_pipe.models.values():
            model.pipeline.set_progress_bar_config(disable=False)
        print("Hunyuan3D-2 shape and texture pipelines loaded successfully.")

    @modal.method()
    def convert(
        self,
        image_bytes: bytes,
        num_inference_steps: int = 30,
        texture: bool = True,
    ) -> dict:
        """
        Input : image_bytes (PNG/JPEG), inference steps, texture flag
        Output: { "glb_bytes": bytes, "error": str | None }
        """
        import torch
        from hy3dgen.shapegen import FaceReducer
        from PIL import Image as PILImage

        call_id = modal.current_function_call_id()
        stage = "preparing image"
        try:
            torch.cuda.empty_cache()

            # Keep all expensive preprocessing inside the spawned GPU job so
            # the browser-facing endpoint can return before Modal's 150 s
            # Web Function timeout.
            with conversion_stage(call_id, stage):
                try:
                    image_bytes = remove_background(image_bytes)
                except Exception as exc:
                    print(f"Background removal unavailable; using original image: {exc}")
                pil_img = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")

            # Stage 1: Shape generation
            stage = "generating shape"
            with conversion_stage(call_id, stage), torch.inference_mode():
                mesh = self.shape_pipe(
                    image=pil_img,
                    num_inference_steps=num_inference_steps,
                    octree_resolution=256,
                )[0]
            if not len(mesh.faces):
                raise ValueError("Shape generation returned an empty mesh")

            # Stage 2: Texture synthesis (optional but default)
            if texture:
                stage = "simplifying mesh"
                with conversion_stage(call_id, stage):
                    original_faces = len(mesh.faces)
                    if original_faces > MAX_TEXTURE_FACES:
                        mesh = FaceReducer()(mesh, max_facenum=MAX_TEXTURE_FACES)
                    print(f"Texture mesh: {original_faces} → {len(mesh.faces)} faces", flush=True)
                    # FaceReducer preserves topology, so pathological inputs can
                    # remain above its target. Do not send them to costly UV unwrap.
                    if not 0 < len(mesh.faces) <= MAX_TEXTURE_FACES:
                        raise ValueError("Mesh could not be simplified for texture generation")
                stage = "synthesizing texture"
                with conversion_stage(call_id, stage), torch.inference_mode():
                    mesh = self.tex_pipe(mesh, image=pil_img)

            # Export to GLB bytes
            stage = "exporting model"
            with conversion_stage(call_id, stage):
                glb_bytes = mesh.export(file_type="glb")
                if not glb_bytes or glb_bytes[:4] != b"glTF":
                    raise ValueError("Export did not produce a valid GLB header")

            print(f"GLB export complete — {len(glb_bytes) / 1024:.1f} KB")
            return {"glb_bytes": glb_bytes, "error": None}

        except Exception as exc:
            traceback.print_exc()
            return {"glb_bytes": None, "error": f"3D conversion failed while {stage}: {exc}"}


# ── A10G variant (Normal mode) ─────────────────────────────────────────────────

@app.cls(
    gpu="A10G",
    cpu=4,
    memory=16384,
    volumes={"/model-cache": threed_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=GPU_TIMEOUT_SECONDS,
    scaledown_window=1200,
)
class ThreeDAgentA10G(_ThreeDAgentBase):
    """Hunyuan3D-2 on A10G (24 GB VRAM) — Normal mode."""

@app.cls(
    gpu="A100",
    cpu=4,
    memory=16384,
    volumes={"/model-cache": threed_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=GPU_TIMEOUT_SECONDS,
    scaledown_window=1200,
)
class ThreeDAgentA100(_ThreeDAgentBase):
    """Hunyuan3D-2 on A100 (40 GB VRAM) — Pro mode."""


# ── H100 variant (Pro Max mode) ───────────────────────────────────────────────
# H100 (80 GB VRAM) gives 2-3× speedup over A10G for diffusion-based 3D generation.

@app.cls(
    gpu="H100",
    cpu=4,
    memory=16384,
    volumes={"/model-cache": threed_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=GPU_TIMEOUT_SECONDS,
    scaledown_window=1200,  # retain loaded pipelines to avoid repeated cold starts
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
    request_id: str | None = None
    speed_mode: Literal["normal", "pro", "promax"] = "pro"
    texture: bool = True          # False = shape-only (faster, no colour)
    num_inference_steps: int = Field(default=30, ge=1, le=100)


def _agent_for_mode(speed_mode: str):
    if speed_mode == "promax":
        return ThreeDAgentH100()
    if speed_mode == "pro":
        return ThreeDAgentA100()
    if speed_mode == "normal":
        return ThreeDAgentA10G()
    raise HTTPException(status_code=422, detail=f"Unknown speed_mode: {speed_mode}")


def _encode_result(result: dict) -> dict:
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


def _decode_image(encoded: str) -> bytes:
    from PIL import Image as PILImage

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image") from exc
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is empty")
    try:
        with PILImage.open(io.BytesIO(image_bytes)) as image:
            image.verify()
    except (OSError, ValueError, PILImage.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or unsupported image") from exc
    return image_bytes


@web_app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": HUNYUAN_MODEL_ID,
        "modes": {
            "normal": "A10G",
            "pro": "A100",
            "promax": "H100",
        },
    }


@web_app.post("/convert")
def convert(req: ConvertRequest) -> dict:
    """
    Returns base64-encoded .glb bytes.
    Routes to A10G, A100 or H100 according to speed mode.
    """
    try:
        # 1. Decode image
        image_bytes = _decode_image(req.image_base64)

        # 2. Route to correct GPU tier
        agent = _agent_for_mode(req.speed_mode)

        result = agent.convert.remote(
            image_bytes=image_bytes,
            num_inference_steps=req.num_inference_steps,
            texture=req.texture,
        )

        return _encode_result(result)

    except HTTPException:
        raise
    except Exception as exc:
        return {"glb_base64": None, "error": f"ConversionFailed: {exc}"}


@web_app.post("/convert/start", status_code=202)
def start_convert(req: ConvertRequest) -> dict:
    """Start a conversion without holding a CORS request open for >150 s."""
    image_bytes = _decode_image(req.image_base64)

    # A browser may retry this endpoint after losing the response, and a page
    # refresh loses React's in-memory "converting" flag. Reuse the original
    # Modal call so either case cannot start another expensive GPU job.
    if req.request_id:
        existing_call_id = conversion_jobs.get(req.request_id)
        if existing_call_id:
            try:
                existing_call = modal.FunctionCall.from_id(existing_call_id)
                # A timeout means the job is genuinely still queued/running.
                # A completed result is also safe to reuse until the browser
                # retrieves it. Cancelled/failed/stale calls must be replaced.
                existing_result = existing_call.get(timeout=0)
            except TimeoutError:
                return {
                    "call_id": existing_call_id,
                    "status": "processing",
                    "reused": True,
                }
            except Exception:
                conversion_jobs.pop(req.request_id, None)
            else:
                # Inference failures are returned as data by convert(), so a
                # completed Modal call is not necessarily a successful model.
                if not existing_result.get("error") and existing_result.get("glb_bytes"):
                    return {
                        "call_id": existing_call_id,
                        "status": "done",
                        "reused": True,
                    }
                conversion_jobs.pop(req.request_id, None)

    agent = _agent_for_mode(req.speed_mode)
    call = agent.convert.spawn(
        image_bytes=image_bytes,
        num_inference_steps=req.num_inference_steps,
        texture=req.texture,
    )
    if req.request_id:
        conversion_jobs[req.request_id] = call.object_id
    return {"call_id": call.object_id, "status": "processing", "reused": False}


@web_app.get("/convert/result/{call_id}")
def conversion_result(call_id: str):
    """Poll a spawned conversion; 202 means it is still running."""
    try:
        call = modal.FunctionCall.from_id(call_id)
        result = call.get(timeout=0)
    except TimeoutError:
        progress = {}
        try:
            progress = conversion_progress.get(call_id) or {}
        except Exception:
            pass
        return JSONResponse(status_code=202, content={"status": "processing", **progress})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "error": f"ConversionFailed: {exc}"},
        )

    encoded = _encode_result(result)
    if encoded.get("error"):
        return JSONResponse(status_code=500, content={"status": "failed", **encoded})
    return {"status": "done", **encoded}


@app.function(image=image, timeout=1200)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
