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
from pydantic import BaseModel, Field

# ── Constants ─────────────────────────────────────────────────────────────────

SAM2_MODEL_ID = "facebook/sam2.1-hiera-large"
SAM2_CACHE_PATH = "/model-cache/sam2"

VLM_MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
VLM_CACHE_PATH = "/model-cache/qwen-vl-7b"
AGENT_CONFIG_PATH = "/root/agent-config/interactive-agent"
GLOBAL_CONFIG_PATH = "/root/agent-config/global"

# ── Volumes ───────────────────────────────────────────────────────────────────

vlm_vol = modal.Volume.from_name("vlm-weights-vol", create_if_missing=True)

# ── Container Image ───────────────────────────────────────────────────────────

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6")
    .pip_install(
        "torch>=2.4.0",
        "torchvision>=0.19.0",
        "transformers>=4.49.0,<5",
        "accelerate>=0.34.0",
        "huggingface_hub>=0.26.0",
        "safetensors>=0.4.5",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
        "Pillow>=10.4.0",
        "numpy>=1.26.0",
        "opencv-python-headless>=4.10.0",
        "qwen-vl-utils>=0.0.8",
        "lm-format-enforcer>=0.10.9",
        "sentence-transformers>=3.2.0",
        "psycopg2-binary>=2.9.9",
        "requests>=2.32.0",
    )
    .add_local_python_source("shared")
    .add_local_dir(
        "anatomy",
        remote_path="/root/anatomy",
        ignore=["**/__pycache__/**", "**/*.pyc"],
    )
    .add_local_file("agents/interactive-agent/SKILL.md", f"{AGENT_CONFIG_PATH}/SKILL.md")
    .add_local_file("agents/interactive-agent/MEMENTO.md", f"{AGENT_CONFIG_PATH}/MEMENTO.md")
    .add_local_file("agents/interactive-agent/PERSONA.md", f"{AGENT_CONFIG_PATH}/PERSONA.md")
    .add_local_file("config/global/PERSONA.md", f"{GLOBAL_CONFIG_PATH}/PERSONA.md")
    .add_local_file("config/global/SKILL.md", f"{GLOBAL_CONFIG_PATH}/SKILL.md")
    .add_local_file("config/global/MEMENTO.md", f"{GLOBAL_CONFIG_PATH}/MEMENTO.md")
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
                )
            else:
                # box coords = [x1, y1, x2, y2] in 0..1 -> scale to image pixels
                bx1, by1 = coords[0] * w, coords[1] * h
                bx2, by2 = coords[2] * w, coords[3] * h
                input_boxes = [[[bx1, by1, bx2, by2]]]  # 3 levels: [batch, box, [x1,y1,x2,y2]]
                inputs = self.processor(
                    images=[pil_img],
                    input_boxes=input_boxes,
                    return_tensors="pt",
                )

            # SAM2 image encoder is bfloat16 but the processor emits float32.
            # Only cast pixel_values — coordinate tensors must stay in their
            # native dtype (float32 / int64) for SAM2's prompt encoder.
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
            if "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].to(dtype=torch.bfloat16)

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
    scaledown_window=300,
)
class SAM2AgentA10G(_SAM2AgentBase):
    """SAM 2 segmentation agent on A10G (Normal / Pro modes)."""

@app.cls(
    gpu="A100",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=60,
    scaledown_window=300,
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
        from shared.memory import MemoryManager

        memory = MemoryManager(
            agent_name="interactive-agent",
            skill_path=Path(AGENT_CONFIG_PATH) / "SKILL.md",
            memento_path=Path(AGENT_CONFIG_PATH) / "MEMENTO.md",
            global_root=GLOBAL_CONFIG_PATH,
        )
        self.agent_context = memory.load_static_context()
        print("Qwen2.5-VL loaded successfully.")

    @modal.method()
    def analyze(
        self,
        image_bytes: bytes,
        highlighted_image_bytes: bytes,
        mode: str,
        question: Optional[str] = None,
        rag_context: Optional[str] = None,
        identified_concept: Optional[str] = None,
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

            from shared.token_budget import TokenBudgetController

            prompt_text = TokenBudgetController().assemble("interactive_agent", {
                "system": "\n\n".join(filter(None, [
                    self.agent_context["system_persona"],
                    "Your active role is to answer using visible evidence from the highlighted educational image.",
                ])),
                "skill_rules": self.agent_context["skill_rules"],
                "memento": self.agent_context["memento"],
                "rag_context": (
                    f"Identified concept: {identified_concept or 'unknown'}\n"
                    "Treat this reference as supporting context, not as visual evidence:\n"
                    f"{rag_context}"
                    if rag_context else ""
                ),
                "mode_instruction": prompt_text,
                "user_question": question or "",
            })

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

    @modal.method()
    def auto_label(
        self,
        original_bytes: bytes,
        crop_bytes: list[bytes],
        region_ids: list[str],
        organ: str,
        view: str,
    ) -> dict[str, Any]:
        """Name marker-grounded anatomy points in one constrained multi-image call."""
        import json
        import torch
        from PIL import Image
        from qwen_vl_utils import process_vision_info
        from lmformatenforcer import CharacterLevelParserConfig, JsonSchemaParser
        from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
        from shared.json_utils import strip_json_fence

        try:
            if not crop_bytes or len(crop_bytes) != len(region_ids) or len(crop_bytes) > 4:
                raise ValueError("Automatic labeling requires one to four crops with matching region IDs")
            images = [Image.open(io.BytesIO(original_bytes)).convert("RGB")]
            images.extend(Image.open(io.BytesIO(value)).convert("RGB") for value in crop_bytes)
            output_schema = {
                "type": "object",
                "additionalProperties": False,
                "required": ["regions"],
                "properties": {
                    "regions": {
                        "type": "array",
                        "maxItems": len(region_ids),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["region_id", "label", "confidence", "visible"],
                            "properties": {
                                "region_id": {"type": "string", "enum": region_ids},
                                "label": {"type": "string", "maxLength": 80},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "visible": {"type": "boolean"},
                            },
                        },
                    },
                },
            }
            instruction = (
                f"The original image shows human {organ or 'anatomy'}"
                + (f" in {view} view. " if view else ". ")
                + f"Image 1 is the complete clean image and provides global context. Images 2 onward are "
                f"overlapping context crops {', '.join(region_ids)}, in that exact order. Each crop contains a cyan ring. "
                "Identify only the specific human anatomical structure directly under the empty CENTER of that "
                "ring; the ring itself is an interface marker, not anatomy. Use the surrounding crop and Image 1 "
                "only as context. Never name a nearby structure that does not pass through the ring center. "
                "If the ring center is background, a boundary between structures, ambiguous, or has no specific "
                "structure, omit it. Return at most the 8 clearest unique structures. Return each anatomical "
                "label at most once, using the crop where it is clearest. Use concise anatomical names only. "
                "Return JSON only matching: "
                + json.dumps(output_schema, separators=(",", ":"))
            )
            content: list[dict[str, Any]] = []
            for image_value in images:
                content.append({"type": "image", "image": image_value})
            content.append({"type": "text", "text": instruction})
            messages = [{"role": "user", "content": content}]
            text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = self.processor(
                text=[text], images=image_inputs, videos=video_inputs,
                padding=True, return_tensors="pt",
            ).to("cuda")
            parser = JsonSchemaParser(
                output_schema,
                config=CharacterLevelParserConfig(
                    max_consecutive_whitespaces=1,
                    force_json_field_order=True,
                    max_json_array_length=len(region_ids),
                ),
            )
            prefix_fn = build_transformers_prefix_allowed_tokens_fn(self.processor.tokenizer, parser)
            with torch.no_grad():
                generated = self.model.generate(
                    **inputs,
                    max_new_tokens=768,
                    do_sample=False,
                    prefix_allowed_tokens_fn=prefix_fn,
                    pad_token_id=self.processor.tokenizer.eos_token_id,
                )
            raw = self.processor.decode(
                generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True,
            )
            parsed = json.loads(strip_json_fence(raw))
            return {"payload": parsed, "error": None}
        except Exception as exc:
            return {"payload": None, "error": f"AutoLabelingFailed: {exc}"}

    @modal.method()
    def localize_structure(
        self,
        image_bytes: bytes,
        organ: str,
        view: str,
        view_requirements: list[str],
        target: dict[str, str],
    ) -> dict[str, Any]:
        """Locate a single canonical structure using Qwen2.5-VL with JSON schema enforcement."""
        import io
        import json
        import torch
        from PIL import Image
        from qwen_vl_utils import process_vision_info
        from lmformatenforcer import CharacterLevelParserConfig, JsonSchemaParser
        from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
        from shared.json_utils import parse_json_with_retry

        try:
            img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_w, img_h = img_pil.size

            output_schema = {
                "type": "object",
                "additionalProperties": False,
                "required": ["view_matches", "view_confidence", "annotations"],
                "properties": {
                    "view_matches": {"type": "boolean"},
                    "view_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "annotations": {
                        "type": "array",
                        "maxItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["structure_id", "bbox", "confidence"],
                            "properties": {
                                "structure_id": {"type": "string", "enum": [target["id"]]},
                                "bbox": {
                                    "type": "array",
                                    "minItems": 4,
                                    "maxItems": 4,
                                    "items": {"type": "number", "minimum": 0, "maximum": 1000},
                                },
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            },
                        },
                    },
                },
            }

            cues_str = json.dumps(view_requirements, ensure_ascii=False)
            instruction = (
                f"This image is {img_w}x{img_h}px showing a {organ} in {view} view. "
                f"Required visual cues: {cues_str}. "
                "Set view_matches=false when required cues are absent. "
                f"Locate the target structure: {target.get('label', target['id'])}. "
                f"Express bbox [left,top,right,bottom] on 0-1000 scale where "
                f"1000={img_w}px wide and {img_h}px tall. "
                "Return target ONLY when its visible boundary is unmistakable. "
                "Omit if hidden or ambiguous. "
                f"Target: {json.dumps([target], ensure_ascii=False)}\n"
                f"Return JSON only: {json.dumps(output_schema, separators=(',', ':'))}"
            )

            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": img_pil},
                    {"type": "text", "text": instruction},
                ],
            }]
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

            parser = JsonSchemaParser(
                output_schema,
                config=CharacterLevelParserConfig(
                    max_consecutive_whitespaces=1,
                    force_json_field_order=True,
                    max_json_array_length=1,
                ),
            )
            pfn = build_transformers_prefix_allowed_tokens_fn(
                self.processor.tokenizer, parser
            )
            with torch.no_grad():
                gen = self.model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    prefix_allowed_tokens_fn=pfn,
                    pad_token_id=self.processor.tokenizer.eos_token_id,
                )
            raw = self.processor.decode(
                gen[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
            )
            parsed, _ = parse_json_with_retry(raw, lambda c: raw, instruction, 1)
            if isinstance(parsed, dict):
                return {
                    "annotations": parsed.get("annotations") or [],
                    "view_matches": parsed.get("view_matches") is True,
                    "view_confidence": parsed.get("view_confidence", 0.0),
                    "error": None,
                }
            return {"annotations": [], "view_matches": True, "error": "InvalidJSON"}
        except Exception as exc:
            return {"annotations": [], "view_matches": True, "error": str(exc)}


# ── VLM A10G variant (Normal mode) ───────────────────────────────────────────────

@app.cls(
    gpu="A100",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=300,
    scaledown_window=300,
)
class VLMAgentA100(_VLMAgentBase):
    """Qwen2.5-VL-7B visual understanding agent on A100 (Pro / Pro Max modes)."""

@app.cls(
    gpu="A10G",
    volumes={"/model-cache": vlm_vol},
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=300,
    scaledown_window=300,
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
    scaledown_window=300,
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


def create_box_highlighted_image(image_bytes: bytes, coords: list[float]) -> tuple[bytes, list[float]]:
    """Highlight the user's rectangle directly, without semantic segmentation."""
    from PIL import Image, ImageDraw

    if len(coords) != 4:
        raise ValueError("Box interaction requires [x1, y1, x2, y2]")
    values = [max(0.0, min(1.0, float(value))) for value in coords]
    x1, x2 = sorted((values[0], values[2]))
    y1, y2 = sorted((values[1], values[3]))
    if x2 - x1 < 0.005 or y2 - y1 < 0.005:
        raise ValueError("Selected region is too small")

    image_value = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = image_value.size
    box = [round(x1 * width), round(y1 * height), round(x2 * width), round(y2 * height)]
    overlay = Image.new("RGBA", image_value.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    stroke_width = max(3, round(min(width, height) * 0.006))
    draw.rectangle(box, fill=(0, 225, 255, 55), outline=(0, 255, 255, 255), width=stroke_width)
    highlighted = Image.alpha_composite(image_value, overlay).convert("RGB")
    buffer = io.BytesIO()
    highlighted.save(buffer, format="PNG")
    return buffer.getvalue(), [x1, y1, x2, y2]


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
    pipeline_run_id: Optional[str] = None
    enable_rag: bool = True


@web_app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "segmentation_model": SAM2_MODEL_ID,
        "vlm_model": VLM_MODEL_ID,
        "automatic_labeling": "four_batches_full_image_plus_four_marker_crops_qwen_vl",
        "manual_interaction": "tap_sam2_then_qwen_vl; box_direct_to_qwen_vl",
    }


@web_app.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    try:
        # 1. Decode base64 image
        image_bytes = base64.b64decode(req.image_base64)

        # 2. Call SAM2 agent — A100 for Pro Max, A10G for Normal/Pro
        mask_bytes: bytes | None = None
        if req.interaction.type == "point":
            sam_agent = SAM2AgentA100() if req.speed_mode == "promax" else SAM2AgentA10G()
            sam_res = sam_agent.segment.remote(
                image_bytes=image_bytes,
                interaction_type="point",
                coords=req.interaction.coords,
            )
            if sam_res.get("error") or not sam_res.get("mask_bytes"):
                return {
                    "mask_base64": None,
                    "response_text": None,
                    "error": sam_res.get("error") or "Segmentation produced no mask",
                }
            mask_bytes = sam_res["mask_bytes"]
            highlighted_bytes = create_highlighted_image(image_bytes, mask_bytes)
            interaction_bbox = sam_res.get("bbox")
        else:
            highlighted_bytes, interaction_bbox = create_box_highlighted_image(
                image_bytes, req.interaction.coords,
            )

        # 4. Call VLM agent — A10G for Normal, A100 for Pro, H100 for Pro Max
        if req.speed_mode == "normal":
            vlm_agent = VLMAgentA10G()
        elif req.speed_mode == "promax":
            vlm_agent = VLMAgentH100()
        else:  # "pro"
            vlm_agent = VLMAgentA100()
        identify_res = vlm_agent.analyze.remote(
            image_bytes=image_bytes,
            highlighted_image_bytes=highlighted_bytes,
            mode="identify",
            question=None,
            rag_context=None,
            identified_concept=None,
        )
        raw_identification = (identify_res.get("response_text") or "").strip()
        identified_concept = raw_identification.splitlines()[0].strip("#*-: ")[:120]
        rag_chunks: list[dict[str, Any]] = []
        rag_context = ""
        if req.enable_rag and identified_concept:
            try:
                from shared.rag import hybrid_retrieve, jina_scrape
                from shared.token_budget import enforce_budget
                rag_chunks = hybrid_retrieve(identified_concept, n=3)
                rag_context = "\n\n".join(str(chunk.get("content") or "") for chunk in rag_chunks)
                if len(rag_context.strip()) < 50:
                    rag_context = jina_scrape(identified_concept)
                rag_context = enforce_budget(rag_context, 300)
            except Exception:
                rag_chunks = []
                rag_context = ""

        vlm_res = vlm_agent.analyze.remote(
            image_bytes=image_bytes,
            highlighted_image_bytes=highlighted_bytes,
            mode=req.mode,
            question=req.question,
            rag_context=rag_context,
            identified_concept=identified_concept,
        )

        if vlm_res.get("error"):
            return {
                "mask_base64": base64.b64encode(mask_bytes).decode("utf-8") if mask_bytes else None,
                "highlighted_base64": base64.b64encode(highlighted_bytes).decode("utf-8"),
                "response_text": None,
                "error": vlm_res["error"],
            }

        response_payload = {
            "mask_base64": base64.b64encode(mask_bytes).decode("utf-8") if mask_bytes else None,
            "highlighted_base64": base64.b64encode(highlighted_bytes).decode("utf-8"),
            "response_text": vlm_res["response_text"],
            "bbox": interaction_bbox,
            "identified_concept": identified_concept or None,
            "rag_sources": [chunk.get("source") for chunk in rag_chunks],
            "error": None,
        }
        try:
            from shared.db import insert_interaction_log
            coords = req.interaction.coords
            insert_interaction_log(
                pipeline_run_id=req.pipeline_run_id,
                click_x=coords[0] if coords else None,
                click_y=coords[1] if len(coords) > 1 else None,
                mode=req.mode,
                user_question=req.question,
                identified_concept=identified_concept or None,
                vlm_response=vlm_res.get("response_text"),
                rag_chunks_used=[chunk["id"] for chunk in rag_chunks if chunk.get("id")],
            )
        except Exception:
            pass
        return response_payload

    except Exception as exc:
        return {
            "mask_base64": None,
            "highlighted_base64": None,
            "response_text": None,
            "error": f"InteractiveAnalysisFailed: {exc}",
        }

# ── Anatomy localization endpoint ────────────────────────────────────────────

# Label placement constants (normalized 0-1 to match SVG viewBox 0-1000)
_LABEL_MARGIN_LEFT   = 0.02    # left-side label left edge
_LABEL_MARGIN_RIGHT  = 0.70    # right-side label left edge
_LABEL_WIDTH         = 0.28
_LABEL_HEIGHT        = 0.055
_LABEL_PADDING       = 0.012


def _place_labels(annotations: list[dict]) -> list[dict]:
    """Bilateral label placement using organ-relative center split.

    Labels are split left/right based on each anchor's position relative to
    the MEDIAN anchor_x across all annotations — this is the organ's true
    horizontal center, regardless of where it sits in the canvas.
    Structures left of organ center → left-margin labels.
    Structures right of organ center → right-margin labels.
    Within each side, labels stack top-to-bottom aligned to their anchor Y,
    sweeping downward to avoid overlaps.
    """
    if not annotations:
        return annotations

    xs = [item["anchor_x"] for item in annotations]
    organ_cx = float(sorted(xs)[len(xs) // 2])

    occupied_left:  list[tuple[float, float]] = []
    occupied_right: list[tuple[float, float]] = []

    for item in sorted(annotations, key=lambda a: a["anchor_y"]):
        ax, ay = item["anchor_x"], item["anchor_y"]
        use_left = ax <= organ_cx
        lx       = _LABEL_MARGIN_LEFT if use_left else _LABEL_MARGIN_RIGHT
        occupied = occupied_left if use_left else occupied_right

        half   = _LABEL_HEIGHT / 2
        ly_top = max(0.01, min(0.97 - _LABEL_HEIGHT, ay - half))

        changed = True
        while changed:
            changed = False
            ly_bot = ly_top + _LABEL_HEIGHT
            for (ot, ob) in occupied:
                if ly_top < ob and ly_bot > ot:
                    ly_top = ob + _LABEL_PADDING
                    ly_top = min(0.97 - _LABEL_HEIGHT, ly_top)
                    changed = True

        item["label_x"] = lx
        item["label_y"] = ly_top + half
        occupied.append((ly_top, ly_top + _LABEL_HEIGHT))

    return annotations


class LocalizeStructureItem(BaseModel):
    id: str
    label: str = ""


class LocalizeStructuresRequest(BaseModel):
    image_base64: str
    organ: str
    view: str
    view_description: str = ""
    structures: list[LocalizeStructureItem] = []
    speed_mode: str = "pro"


@web_app.post("/localize-structures")
def localize_structures(req: LocalizeStructuresRequest) -> dict:
    # Retained only for older clients.  New clients use /grid-labels, which has
    # no anatomy catalog dependency and cannot raise ModuleNotFoundError here.
    return {
        "annotations": [],
        "organ": req.organ,
        "view": req.view,
        "error": "DeprecatedEndpoint: use /grid-labels",
    }

    try:
        import math
        import numpy as np
        from PIL import Image as _PIL
        from anatomy import canonicalize_structure, get_structure, get_view  # type: ignore
        from anatomy.grid_localization import inner_grid_points, keep_unique_masks  # type: ignore
        from anatomy.localization_quality import filter_localizations  # type: ignore
        from shared.json_utils import parse_json_with_retry  # type: ignore

        image_bytes = base64.b64decode(req.image_base64, validate=True)
        if not image_bytes:
            raise HTTPException(status_code=422, detail={"error": "EmptyImage"})

        # Resolve target structures
        view_meta = get_view(req.organ, req.view)
        requested = [item.id for item in req.structures] or list(view_meta["required_structures"])
        targets: list[dict] = []
        for value in requested:
            canonical = canonicalize_structure(req.organ, value)
            if not canonical:
                continue
            structure = get_structure(req.organ, canonical)
            if canonical not in {t["id"] for t in targets}:
                targets.append({"id": canonical, "label": structure["label"]})

        # Detect organ bounds from pixel contrast so VLM knows where in the
        # image the organ actually sits. Without this Qwen assumes center=(0.5,0.5)
        # but generated images often position the organ right-of-center, causing
        # all bboxes to cluster on the wrong side.
        organ_region_hint = ""
        try:
            _img = _PIL.open(io.BytesIO(image_bytes)).convert("RGB")
            _rgb = np.asarray(_img, dtype=np.float32)
            _h, _w = _rgb.shape[:2]
            _border = np.concatenate((_rgb[0], _rgb[-1], _rgb[:, 0], _rgb[:, -1]), axis=0)
            _bg    = np.median(_border, axis=0)
            _cont  = np.linalg.norm(_rgb - _bg, axis=2)
            _fg    = _cont > 28.0
            if _fg.any():
                _rows = np.where(_fg.any(axis=1))[0]
                _cols = np.where(_fg.any(axis=0))[0]
                _ox1  = max(0,    int(_cols[0]  / _w * 1000) - 10)
                _oy1  = max(0,    int(_rows[0]  / _h * 1000) - 10)
                _ox2  = min(1000, int(_cols[-1] / _w * 1000) + 10)
                _oy2  = min(1000, int(_rows[-1] / _h * 1000) + 10)
                organ_region_hint = (
                    f"organ occupies image region [{_ox1},{_oy1},{_ox2},{_oy2}] "
                    f"on the 0-1000 grid (image is {_w}x{_h}px); "
                    "all bbox coordinates must fall within this region"
                )
        except Exception:
            pass

        # Choose VLM based on speed mode
        if req.speed_mode == "normal":
            vlm_agent = VLMAgentA10G()
        elif req.speed_mode == "promax":
            vlm_agent = VLMAgentH100()
        else:
            vlm_agent = VLMAgentA100()

        # Grid-first localization: prompt SAM exactly at the centres of the
        # inner 4x4 cells of a 6x6 grid.  The outer ring is deliberately
        # ignored because it is typically background.  Deduplication means a
        # large structure hit by several centre points is sent to Qwen only
        # once, rather than producing repeated labels.
        sam_agent = SAM2AgentA10G() if req.speed_mode != "promax" else SAM2AgentA100()
        grid_candidates: list[dict] = []
        for point in inner_grid_points():
            sam_res = sam_agent.segment.remote(
                image_bytes=image_bytes,
                interaction_type="point",
                coords=[point["x"], point["y"]],
            )
            if not sam_res.get("error") and isinstance(sam_res.get("bbox"), list):
                grid_candidates.append({**point, "bbox": sam_res["bbox"]})
        grid_candidates = keep_unique_masks(grid_candidates)

        requested_view = (req.view_description or "").strip()
        effective_view = requested_view or view_meta["id"]
        base_requirements = (
            [f"user-requested viewpoint: {requested_view}"]
            if requested_view else list(view_meta.get("clean_image_rules") or [])
        )
        if organ_region_hint:
            base_requirements = list(base_requirements) + [organ_region_hint]

        # Call VLM once per structure (avoids list-completion hallucination)
        localized_rows: list[dict] = []
        for idx, target in enumerate(targets):
            res = vlm_agent.localize_structure.remote(
                image_bytes=image_bytes,
                organ=req.organ,
                view=effective_view,
                view_requirements=base_requirements,
                target=target,
            )
            if res.get("error"):
                continue
            if idx == 0 and not res.get("view_matches"):
                return {
                    "annotations": [],
                    "organ": req.organ,
                    "view": effective_view,
                    "error": "GeneratedImageViewMismatch",
                }
            if not res.get("view_matches"):
                continue
            for row in res.get("annotations") or []:
                if isinstance(row, dict):
                    localized_rows.append(row)

        # Normalize bboxes, build annotation list
        target_map = {t["id"]: t for t in targets}
        annotations: list[dict] = []
        for raw in localized_rows:
            if not isinstance(raw, dict):
                continue
            canonical = canonicalize_structure(req.organ, str(raw.get("structure_id") or ""))
            bbox = raw.get("bbox")
            if canonical not in target_map or not isinstance(bbox, list) or len(bbox) != 4:
                continue
            try:
                confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
                coords = [float(v) for v in bbox]
                if all(abs(v) <= 1.0 for v in coords):
                    x1r, y1r, x2r, y2r = coords
                else:
                    x1r, y1r, x2r, y2r = (c / 1000.0 for c in coords)
                x1 = max(0.0, min(1.0, x1r))
                y1 = max(0.0, min(1.0, y1r))
                x2 = max(0.0, min(1.0, x2r))
                y2 = max(0.0, min(1.0, y2r))
                clean_bbox = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
                ax = (clean_bbox[0] + clean_bbox[2]) / 2
                ay = (clean_bbox[1] + clean_bbox[3]) / 2
            except (TypeError, ValueError):
                continue
            annotations.append({
                "structure_id": f"{req.organ}.{canonical}",
                "label": target_map[canonical]["label"],
                "anchor_x": ax,
                "anchor_y": ay,
                "bbox": clean_bbox,
                "confidence": confidence,
                "verified": False,
            })

        # A Qwen proposal is accepted only if it can be grounded to a distinct
        # SAM mask originating from one of the 16 inner grid prompts.  This
        # prevents labels from appearing over the clean image from guessed or
        # repeated VLM coordinates.
        if grid_candidates:
            grounded_by_grid: list[dict] = []
            for annotation in annotations:
                matches = [
                    candidate for candidate in grid_candidates
                    if candidate["bbox"][0] <= annotation["anchor_x"] <= candidate["bbox"][2]
                    and candidate["bbox"][1] <= annotation["anchor_y"] <= candidate["bbox"][3]
                ]
                if not matches:
                    continue
                candidate = min(matches, key=lambda item: (item["x"] - annotation["anchor_x"]) ** 2 + (item["y"] - annotation["anchor_y"]) ** 2)
                annotation["grid_index"] = candidate["grid_index"]
                annotation["grid_row"] = candidate["grid_row"]
                annotation["grid_column"] = candidate["grid_column"]
                annotation["grounding"] = "sam2_6x6_inner_4x4"
                grounded_by_grid.append(annotation)
            annotations = grounded_by_grid

        annotations = filter_localizations(annotations)

        # SAM2 refinement: replace VLM bbox center with mask trimmed-mean centroid
        if annotations and req.speed_mode in ("pro", "promax"):
            sam_agent = SAM2AgentA100() if req.speed_mode == "promax" else SAM2AgentA10G()
            ref_img = _PIL.open(io.BytesIO(image_bytes)).convert("RGB")
            ref_w, ref_h = ref_img.size
            ref_rgb   = np.asarray(ref_img, dtype=np.float32)
            border    = np.concatenate((ref_rgb[0], ref_rgb[-1], ref_rgb[:, 0], ref_rgb[:, -1]), axis=0)
            bg_color  = np.median(border, axis=0)
            fg_contr  = np.linalg.norm(ref_rgb - bg_color, axis=2)
            grounded: list[dict] = []
            for ann in annotations:
                sam_res = sam_agent.segment.remote(
                    image_bytes=image_bytes,
                    interaction_type="box",
                    coords=ann["bbox"],
                )
                if sam_res.get("error") or not sam_res.get("mask_bytes"):
                    px = min(ref_w - 1, max(0, int(ann["anchor_x"] * ref_w)))
                    py = min(ref_h - 1, max(0, int(ann["anchor_y"] * ref_h)))
                    if fg_contr[py, px] >= 35.0:
                        ann["verified"] = True
                        grounded.append(ann)
                    continue
                mask = np.array(_PIL.open(io.BytesIO(sam_res["mask_bytes"])).convert("L")) > 0
                x1b, y1b, x2b, y2b = ann["bbox"]
                pad  = 0.025
                left = max(0, int((x1b - pad) * ref_w))
                top  = max(0, int((y1b - pad) * ref_h))
                right  = min(ref_w, max(left + 1, int((x2b + pad) * ref_w)))
                bottom = min(ref_h, max(top + 1, int((y2b + pad) * ref_h)))
                vis  = mask[top:bottom, left:right] & (fg_contr[top:bottom, left:right] >= 35.0)
                ry, rx = np.where(vis)
                if len(rx) < 8:
                    continue
                px_all = rx + left
                py_all = ry + top
                lo, hi = 10, 90
                xl, xh = np.percentile(px_all, lo), np.percentile(px_all, hi)
                yl, yh = np.percentile(py_all, lo), np.percentile(py_all, hi)
                core = (px_all >= xl) & (px_all <= xh) & (py_all >= yl) & (py_all <= yh)
                cx = px_all[core] if core.any() else px_all
                cy = py_all[core] if core.any() else py_all
                ann["anchor_x"] = float(cx.mean() / ref_w)
                ann["anchor_y"] = float(cy.mean() / ref_h)
                ann["bbox"] = [
                    float(px_all.min() / ref_w), float(py_all.min() / ref_h),
                    float(px_all.max() / ref_w), float(py_all.max() / ref_h),
                ]
                ann["grounding"] = "sam2_trimmed_mean"
                ann["verified"] = True
                grounded.append(ann)
            annotations = filter_localizations(grounded)

        annotations = _place_labels(annotations)

        return {
            "annotations":    annotations,
            "organ":          req.organ,
            "view":           effective_view,
            "grid": {"size": 6, "inner_cells": 16, "unique_masks": len(grid_candidates)},
            "error":          None,
        }

    except HTTPException:
        raise
    except Exception as exc:
        return {"annotations": [], "organ": req.organ, "view": req.view,
                "error": str(exc)}


class AutoLabelsRequest(BaseModel):
    """Automatic anatomy labels without segmentation."""

    image_base64: str
    organ: str = Field(default="anatomy", max_length=80)
    view: str = Field(default="", max_length=160)
    speed_mode: Literal["normal", "pro", "promax"] = "pro"


@web_app.post("/auto-labels")
def auto_labels(req: AutoLabelsRequest) -> dict:
    """Label 16 inner-grid targets in four grounded Qwen-VL batches."""
    try:
        from anatomy.auto_labeling import build_auto_label_assets, validate_auto_labels

        image_bytes = base64.b64decode(req.image_base64, validate=True)
        if not image_bytes:
            raise HTTPException(status_code=422, detail={"error": "EmptyImage"})
        assets = build_auto_label_assets(image_bytes)
        if req.speed_mode == "normal":
            vlm_agent = VLMAgentA10G()
        elif req.speed_mode == "promax":
            vlm_agent = VLMAgentH100()
        else:
            vlm_agent = VLMAgentA100()
        raw_regions: list[dict[str, Any]] = []
        batch_errors: list[str] = []
        batch_size = 4
        for start in range(0, len(assets["regions"]), batch_size):
            batch_regions = assets["regions"][start:start + batch_size]
            result = vlm_agent.auto_label.remote(
                original_bytes=assets["original_bytes"],
                crop_bytes=assets["crop_bytes"][start:start + batch_size],
                region_ids=[region["region_id"] for region in batch_regions],
                organ=req.organ,
                view=req.view,
            )
            if result.get("error"):
                batch_errors.append(str(result["error"]))
                continue
            payload = result.get("payload")
            if isinstance(payload, dict) and isinstance(payload.get("regions"), list):
                raw_regions.extend(item for item in payload["regions"] if isinstance(item, dict))
        annotations, diagnostics = validate_auto_labels(
            {"regions": raw_regions}, assets["regions"], assets["image_size"],
        )
        total_batches = (len(assets["regions"]) + batch_size - 1) // batch_size
        diagnostics["completed_batches"] = total_batches - len(batch_errors)
        diagnostics["failed_batches"] = len(batch_errors)
        if len(batch_errors) == total_batches:
            return {"annotations": [], "diagnostics": diagnostics, "error": "; ".join(batch_errors)}
        return {
            "annotations": _place_labels(annotations),
            "diagnostics": diagnostics,
            "warnings": batch_errors,
            "content_bbox": [0, 0, assets["image_size"][0], assets["image_size"][1]],
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        return {
            "annotations": [],
            "diagnostics": {"accepted_labels": 0},
            "error": f"AutoLabelingFailed: {exc}",
        }


class GridLabelsRequest(BaseModel):
    """Catalog-free anatomy labels generated from SAM2 masks and Qwen-VL."""

    image_base64: str
    organ: str = "anatomy"
    speed_mode: str = "pro"


def _grid_bbox_iou(first: list[float], second: list[float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    overlap = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - overlap
    return overlap / union if union else 0.0


@web_app.post("/grid-labels")
def grid_labels(req: GridLabelsRequest) -> dict:
    """Segment 16 inner grid centres and let Qwen-VL name each unique mask."""
    try:
        image_bytes = base64.b64decode(req.image_base64, validate=True)
        if not image_bytes:
            raise HTTPException(status_code=422, detail={"error": "EmptyImage"})

        sam_agent = SAM2AgentA100() if req.speed_mode == "promax" else SAM2AgentA10G()
        vlm_agent = VLMAgentA10G() if req.speed_mode == "normal" else (VLMAgentH100() if req.speed_mode == "promax" else VLMAgentA100())
        candidates: list[dict] = []
        for row in range(1, 5):
            for column in range(1, 5):
                x, y = (column + 0.5) / 6, (row + 0.5) / 6
                result = sam_agent.segment.remote(image_bytes=image_bytes, interaction_type="point", coords=[x, y])
                bbox = result.get("bbox")
                if result.get("error") or not isinstance(bbox, list) or len(bbox) != 4:
                    continue
                try:
                    clean_bbox = [max(0.0, min(1.0, float(value))) for value in bbox]
                except (TypeError, ValueError):
                    continue
                if clean_bbox[2] <= clean_bbox[0] or clean_bbox[3] <= clean_bbox[1]:
                    continue
                area = (clean_bbox[2] - clean_bbox[0]) * (clean_bbox[3] - clean_bbox[1])
                if area < 0.0015 or area > 0.65 or any(_grid_bbox_iou(clean_bbox, item["bbox"]) >= 0.80 for item in candidates):
                    continue
                candidates.append({"bbox": clean_bbox, "x": x, "y": y, "grid_index": len(candidates), "grid_row": row, "grid_column": column, "mask_bytes": result.get("mask_bytes")})

        annotations: list[dict] = []
        seen_labels: set[str] = set()
        for candidate in candidates:
            if not candidate["mask_bytes"]:
                continue
            highlighted = create_highlighted_image(image_bytes, candidate["mask_bytes"])
            identified = vlm_agent.analyze.remote(image_bytes=image_bytes, highlighted_image_bytes=highlighted, mode="identify")
            text = (identified.get("response_text") or "").strip()
            label = text.splitlines()[0].strip("#*-: ")[:80]
            normalized = label.casefold()
            if identified.get("error") or len(label) < 2 or normalized in seen_labels:
                continue
            seen_labels.add(normalized)
            bbox = candidate["bbox"]
            annotations.append({
                "structure_id": f"grid.{candidate['grid_row']}.{candidate['grid_column']}",
                "label": label,
                "anchor_x": (bbox[0] + bbox[2]) / 2,
                "anchor_y": (bbox[1] + bbox[3]) / 2,
                "bbox": bbox,
                "confidence": 0.90,
                "verified": True,
                "grounding": "sam2_6x6_inner_4x4_qwen_vl",
                "grid_index": candidate["grid_index"],
                "grid_row": candidate["grid_row"],
                "grid_column": candidate["grid_column"],
            })
        return {"annotations": _place_labels(annotations), "grid": {"size": 6, "inner_cells": 16, "unique_masks": len(candidates)}, "error": None}
    except HTTPException:
        raise
    except Exception as exc:
        return {"annotations": [], "error": f"GridLabelingFailed: {exc}"}



@app.function(
    image=image,
    secrets=[modal.Secret.from_name("supabase-secret")],
)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
