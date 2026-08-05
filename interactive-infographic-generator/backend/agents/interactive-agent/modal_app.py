"""
agents/interactive-agent/modal_app.py
──────────────────────────────────────
Interactive Image Agent
  Models:
    - SAM 2 (facebook/sam2.1-hiera-large via HuggingFace Transformers)
    - Qwen2.5-VL-7B (Qwen/Qwen2.5-VL-7B-Instruct via HuggingFace Transformers)
  GPUs:
    - SAM2Agent: A10G GPU (24 GB VRAM)
    - VLMAgent: A100 GPU (40 GB VRAM)
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any, Literal, Optional

import modal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Constants ─────────────────────────────────────────────────────────────────

SAM2_MODEL_ID = "facebook/sam2.1-hiera-large"
SAM2_CACHE_PATH = "/model-cache/sam2"

VLM_MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
VLM_CACHE_PATH = "/model-cache/qwen-vl-7b"

# ── Volumes ───────────────────────────────────────────────────────────────────

vlm_vol = modal.Volume.from_name("vlm-weights-vol", create_if_missing=True)

# ── Container Image ───────────────────────────────────────────────────────────

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6")
    .pip_install(
        "torch>=2.4.0",
        "torchvision>=0.19.0",
        "transformers>=4.49.0",
        "accelerate>=0.34.0",
        "huggingface_hub>=0.26.0",
        "safetensors>=0.4.5",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "Pillow>=10.4.0",
        "numpy>=1.26.0",
        "opencv-python-headless>=4.10.0",
        "qwen-vl-utils>=0.0.8",
    )
)

app = modal.App("interactive-agent", image=image)

# Reduce CUDA memory fragmentation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"


# ── One-time setup: Download model weights to volume ──────────────────────────

@app.function(
    image=image,
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=3600,
)
def setup_models() -> None:
    """Download Qwen2.5-VL-7B and SAM 2 weights into Modal Volume."""
    from huggingface_hub import snapshot_download

    print(f"Downloading {VLM_MODEL_ID} → {VLM_CACHE_PATH} ...")
    snapshot_download(
        VLM_MODEL_ID,
        local_dir=VLM_CACHE_PATH,
        token=os.environ.get("HF_TOKEN"),
    )

    print(f"Downloading {SAM2_MODEL_ID} → {SAM2_CACHE_PATH} ...")
    snapshot_download(
        SAM2_MODEL_ID,
        local_dir=SAM2_CACHE_PATH,
        token=os.environ.get("HF_TOKEN"),
    )

    vlm_vol.commit()
    print("Done. vlm-weights-vol is ready.")


# ── SAM 2 Agent Class ─────────────────────────────────────────────────────────

class _SAM2AgentBase:
    """SAM 2 segmentation agent on A10G (Normal / Pro modes)."""

    @modal.enter()
    def load_model(self) -> None:
        import torch
        from transformers import AutoProcessor, AutoModelForMaskGeneration

        model_path = (
            SAM2_CACHE_PATH
            if Path(SAM2_CACHE_PATH).exists() and (Path(SAM2_CACHE_PATH) / "config.json").exists()
            else SAM2_MODEL_ID
        )

        print(f"Loading SAM 2 model from {model_path}...")
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.model = AutoModelForMaskGeneration.from_pretrained(
            model_path, torch_dtype=torch.bfloat16
        ).to("cuda")
        self.model.eval()
        print("SAM 2 loaded successfully via Transformers.")

    @modal.method()
    def segment(
        self,
        image_bytes: bytes,
        interaction_type: str,
        coords: list[float],
    ) -> dict[str, Any]:
        """
        Input: image_bytes (PNG/JPEG), interaction_type ("point" | "box"), coords (normalized 0..1)
        Output: {"mask_bytes": bytes, "bbox": [x1, y1, x2, y2], "error": str | None}
        """
        import numpy as np
        import torch
        from PIL import Image

        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = pil_img.size

            if interaction_type == "point":
                # coords = [x, y] in 0..1 -> scale to image pixels
                px, py = coords[0] * w, coords[1] * h
                input_points = [[[[px, py]]]]  # 4 levels: [image, object, point, [x, y]]
                input_labels = [[[1]]]         # 3 levels: [image, object, [1]]
                inputs = self.processor(
                    images=[pil_img],
                    input_points=input_points,
                    input_labels=input_labels,
                    return_tensors="pt",
                ).to("cuda")
            else:
                # box coords = [x1, y1, x2, y2] in 0..1 -> scale to image pixels
                bx1, by1 = coords[0] * w, coords[1] * h
                bx2, by2 = coords[2] * w, coords[3] * h
                input_boxes = [[[bx1, by1, bx2, by2]]]  # 3 levels: [batch, box, [x1,y1,x2,y2]]
                inputs = self.processor(
                    images=[pil_img],
                    input_boxes=input_boxes,
                    return_tensors="pt",
                ).to("cuda")

            with torch.no_grad():
                outputs = self.model(**inputs)

            # Extract best mask using iou_scores if available
            if hasattr(outputs, "iou_scores") and outputs.iou_scores is not None and outputs.iou_scores.numel() > 0:
                best_idx = int(torch.argmax(outputs.iou_scores[0, 0]).item())
                raw_mask_tensor = outputs.pred_masks[0, 0, best_idx]
            else:
                raw_mask_tensor = outputs.pred_masks[0, 0, 0]
            binary_mask_np = (raw_mask_tensor > 0).cpu().numpy().astype(np.uint8) * 255

            mask_pil = Image.fromarray(binary_mask_np, mode="L").resize((w, h), Image.Resampling.NEAREST)
            best_mask = np.array(mask_pil)

            # Calculate bounding box
            y_indices, x_indices = np.where(best_mask > 0)
            if len(x_indices) > 0:
                bbox = [
                    float(x_indices.min() / w),
                    float(y_indices.min() / h),
                    float(x_indices.max() / w),
                    float(y_indices.max() / h),
                ]
            else:
                bbox = coords if interaction_type == "box" else [coords[0]-0.05, coords[1]-0.05, coords[0]+0.05, coords[1]+0.05]

            # Save mask as 1-channel PNG bytes
            mask_pil = Image.fromarray(best_mask, mode="L")
            buf = io.BytesIO()
            mask_pil.save(buf, format="PNG")
            buf.seek(0)

            return {"mask_bytes": buf.read(), "bbox": bbox, "error": None}

        except Exception as exc:
            return {"mask_bytes": None, "bbox": None, "error": f"SAM2SegmentationFailed: {exc}"}


# ── SAM2 A100 variant (Pro Max mode) ──────────────────────────────────────────

@app.cls(
    gpu="A10G",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=120,
    container_idle_timeout=300,
)
class SAM2AgentA10G(_SAM2AgentBase):
    """SAM 2 segmentation agent on A10G (Normal / Pro modes)."""

@app.cls(
    gpu="A100",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=60,
    container_idle_timeout=300,
)
class SAM2AgentA100(_SAM2AgentBase):
    """Same SAM 2 model but on A100 for faster segmentation (Pro Max mode)."""


# ── Qwen2.5-VL Agent Class ───────────────────────────────────────────────────

class _VLMAgentBase:
    """Qwen2.5-VL-7B visual understanding agent on A100 (Pro / Pro Max modes)."""

    @modal.enter()
    def load_model(self) -> None:
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        model_path = (
            VLM_CACHE_PATH
            if Path(VLM_CACHE_PATH).exists() and (Path(VLM_CACHE_PATH) / "config.json").exists()
            else VLM_MODEL_ID
        )

        print(f"Loading Qwen2.5-VL model from {model_path}...")
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.model.eval()
        print("Qwen2.5-VL loaded successfully.")

    @modal.method()
    def analyze(
        self,
        image_bytes: bytes,
        highlighted_image_bytes: bytes,
        mode: str,
        question: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Input: raw image_bytes, highlighted_image_bytes (image with mask overlay), mode, optional question
        Output: {"response_text": str, "error": str | None}
        """
        import torch
        from PIL import Image
        from qwen_vl_utils import process_vision_info

        try:
            highlighted_img = Image.open(io.BytesIO(highlighted_image_bytes)).convert("RGB")

            # Build mode-dependent text prompt
            if mode == "identify":
                prompt_text = (
                    "Look at the highlighted region (cyan overlay/outline) in this educational image. "
                    "Identify what object or concept is highlighted. Provide a concise title and 1-2 sentence description."
                )
            elif mode == "explain":
                prompt_text = (
                    "Look at the highlighted region (cyan overlay/outline) in this educational image. "
                    "Explain what this part is, how it works, and its role in the overall diagram in a clear, educational tone."
                )
            elif mode == "ask":
                user_q = (question or "What is in this region?").strip()
                prompt_text = (
                    f"Regarding the highlighted region (cyan overlay) in this image, please answer this question: '{user_q}'"
                )
            else:
                prompt_text = "Describe the highlighted region in the image."

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": highlighted_img},
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ]

            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to("cuda")

            with torch.no_grad():
                generated_ids = self.model.generate(**inputs, max_new_tokens=256)
                generated_ids_trimmed = [
                    out_ids[len(in_ids) :]
                    for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                output_text = self.processor.batch_decode(
                    generated_ids_trimmed,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )[0]

            return {"response_text": output_text.strip(), "error": None}

        except Exception as exc:
            return {"response_text": None, "error": f"VLMAnalysisFailed: {exc}"}


# ── VLM A10G variant (Normal mode) ───────────────────────────────────────────────

@app.cls(
    gpu="A100",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=300,
    container_idle_timeout=300,
)
class VLMAgentA100(_VLMAgentBase):
    """Qwen2.5-VL-7B visual understanding agent on A100 (Pro / Pro Max modes)."""

@app.cls(
    gpu="A10G",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=300,
    container_idle_timeout=300,
)
class VLMAgentA10G(_VLMAgentBase):
    """Same Qwen2.5-VL-7B model but on A10G (Normal mode, lower cost)."""

# ── VLM H100 variant (Pro Max mode) ──────────────────────────────────────────────
# H100 memory bandwidth (3.35 TB/s vs 2 TB/s on A100) directly accelerates the
# memory-bandwidth-bound decode phase of Qwen2.5-VL-7B inference.

@app.cls(
    gpu="H100",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=120,
    container_idle_timeout=300,
)
class VLMAgentH100(_VLMAgentBase):
    """Qwen2.5-VL-7B on H100 — fastest VLM inference (Pro Max mode)."""


# ── Helper: Overlay Mask on Image ─────────────────────────────────────────────

def create_highlighted_image(image_bytes: bytes, mask_bytes: bytes) -> bytes:
    """Create composite image with cyan mask overlay + bright outline."""
    import numpy as np
    from PIL import Image, ImageFilter

    base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    mask_img = Image.open(io.BytesIO(mask_bytes)).convert("L")

    # Resize mask if needed
    if mask_img.size != base_img.size:
        mask_img = mask_img.resize(base_img.size, Image.Resampling.NEAREST)

    np_base = np.array(base_img)
    np_mask = np.array(mask_img) > 128  # boolean mask

    # Cyan overlay: RGB (0, 225, 255) with alpha ~0.35
    overlay = np_base.copy()
    overlay[np_mask, 0] = (overlay[np_mask, 0] * 0.4 + 0 * 0.6).astype(np.uint8)
    overlay[np_mask, 1] = (overlay[np_mask, 1] * 0.4 + 225 * 0.6).astype(np.uint8)
    overlay[np_mask, 2] = (overlay[np_mask, 2] * 0.4 + 255 * 0.6).astype(np.uint8)

    # Draw cyan contour line
    outline_mask = mask_img.filter(ImageFilter.FIND_EDGES)
    np_outline = np.array(outline_mask) > 50
    overlay[np_outline, 0] = 0
    overlay[np_outline, 1] = 255
    overlay[np_outline, 2] = 255
    overlay[np_outline, 3] = 255

    res_pil = Image.fromarray(overlay, mode="RGBA").convert("RGB")
    buf = io.BytesIO()
    res_pil.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ── FastAPI Application ───────────────────────────────────────────────────────

web_app = FastAPI(
    title="Interactive Image Agent",
    description="Interactive region analysis using SAM 2 + Qwen2.5-VL-7B",
    version="1.0.0",
)

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class InteractionData(BaseModel):
    type: Literal["point", "box"]
    coords: list[float]  # [x, y] for point or [x1, y1, x2, y2] for box (normalized 0..1)


class AnalyzeRequest(BaseModel):
    image_base64: str
    interaction: InteractionData
    mode: Literal["identify", "explain", "ask"] = "identify"
    question: Optional[str] = None
    speed_mode: str = "pro"  # "normal" | "pro" | "promax"


@web_app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "segmentation_model": SAM2_MODEL_ID,
        "vlm_model": VLM_MODEL_ID,
    }


@web_app.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    try:
        # 1. Decode base64 image
        image_bytes = base64.b64decode(req.image_base64)

        # 2. Call SAM2 agent — A100 for Pro Max, A10G for Normal/Pro
        if req.speed_mode == "promax":
            sam_agent = SAM2AgentA100()
        else:
            sam_agent = SAM2AgentA10G()
        sam_res = sam_agent.segment.remote(
            image_bytes=image_bytes,
            interaction_type=req.interaction.type,
            coords=req.interaction.coords,
        )

        if sam_res.get("error") or not sam_res.get("mask_bytes"):
            return {
                "mask_base64": None,
                "response_text": None,
                "error": sam_res.get("error") or "Segmentation produced no mask",
            }

        mask_bytes = sam_res["mask_bytes"]

        # 3. Create composite highlighted image
        highlighted_bytes = create_highlighted_image(image_bytes, mask_bytes)

        # 4. Call VLM agent — A10G for Normal, A100 for Pro, H100 for Pro Max
        if req.speed_mode == "normal":
            vlm_agent = VLMAgentA10G()
        elif req.speed_mode == "promax":
            vlm_agent = VLMAgentH100()
        else:  # "pro"
            vlm_agent = VLMAgentA100()
        vlm_res = vlm_agent.analyze.remote(
            image_bytes=image_bytes,
            highlighted_image_bytes=highlighted_bytes,
            mode=req.mode,
            question=req.question,
        )

        if vlm_res.get("error"):
            return {
                "mask_base64": base64.b64encode(mask_bytes).decode("utf-8"),
                "highlighted_base64": base64.b64encode(highlighted_bytes).decode("utf-8"),
                "response_text": None,
                "error": vlm_res["error"],
            }

        return {
            "mask_base64": base64.b64encode(mask_bytes).decode("utf-8"),
            "highlighted_base64": base64.b64encode(highlighted_bytes).decode("utf-8"),
            "response_text": vlm_res["response_text"],
            "bbox": sam_res.get("bbox"),
            "error": None,
        }

    except Exception as exc:
        return {
            "mask_base64": None,
            "highlighted_base64": None,
            "response_text": None,
            "error": f"InteractiveAnalysisFailed: {exc}",
        }


@app.function(image=image)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
