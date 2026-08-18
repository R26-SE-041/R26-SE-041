"""
agents/eval-agent/modal_app.py
───────────────────────────────
Evaluation Agent
  VLM    : Qwen/Qwen2.5-VL-7B-Instruct  (prompt alignment + educational usefulness)
  Metric : CLIPScore via torchmetrics    (fast quantitative alignment, no FID/PickScore)
  GPU    : A10G  (Qwen2.5-VL-7B ≈14 GB + CLIPScore ≈1.5 GB = ~15.5 GB at fp16)

NOT IMPLEMENTED (by design):
  - FID: requires a reference dataset — invalid without one
  - PickScore: preference model tuned for aesthetics, not educational content

CRITICAL GUARD (Flag 3 from review):
  image_bytes MUST be non-empty bytes before this agent is called.
  The /evaluate endpoint validates this and returns 422 if violated.
  A silent empty-bytes payload would produce a numerically plausible but
  meaningless CLIPScore of ~0.0 and a VLM hallucination.

DEPLOY (from backend/ directory):
    cd backend
    modal deploy agents/eval-agent/modal_app.py
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any

import modal

# ── Constants ─────────────────────────────────────────────────────────────────

VLM_MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"   # exact string — do NOT substitute
VLM_CACHE_PATH = "/root/models/qwen-vl-7b"
CLIP_MODEL_ID = "openai/clip-vit-base-patch16"
MAX_JSON_RETRIES = 2
AGENT_CONFIG_PATH = "/root/agent-config/eval-agent"


# ── Image build ───────────────────────────────────────────────────────────────

def _download_models() -> None:
    """Download both models during image build (not at request time)."""
    from huggingface_hub import snapshot_download
    from transformers import CLIPModel, CLIPProcessor

    print(f"Downloading {VLM_MODEL_ID} ...")
    snapshot_download(VLM_MODEL_ID, local_dir=VLM_CACHE_PATH)

    print(f"Downloading {CLIP_MODEL_ID} ...")
    # torchmetrics downloads CLIP lazily on first call; pre-cache it explicitly
    CLIPModel.from_pretrained(CLIP_MODEL_ID)
    CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
    print("All model downloads complete.")


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers>=4.47.0",
        "qwen-vl-utils>=0.0.8",      # Qwen2.5-VL process_vision_info helper
        "torch>=2.4.0",
        "torchvision>=0.19.0",
        "torchmetrics[multimodal]>=1.5.0",
        "accelerate>=0.34.0",
        "huggingface_hub>=0.26.0",
        "Pillow>=10.4.0",
        "numpy>=1.26.0",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.9.0",
    )
    .run_function(
        _download_models,
        secrets=[modal.Secret.from_name("hf-secret")],
    )
    # Add shared/ package — run `modal deploy` from backend/ so this path resolves
    .add_local_python_source("shared")
    .add_local_file("agents/eval-agent/SKILL.md", f"{AGENT_CONFIG_PATH}/SKILL.md")
    .add_local_file("agents/eval-agent/MEMENTO.md", f"{AGENT_CONFIG_PATH}/MEMENTO.md")
)

app = modal.App("eval-agent", image=image)


# ── Agent class ───────────────────────────────────────────────────────────────

@app.cls(
    gpu="A10G",
    secrets=[modal.Secret.from_name("hf-secret")],
    timeout=180,
    scaledown_window=300,
)
class EvalAgent:
    """
    Dual-metric evaluation agent:
      1. CLIPScore — fast quantitative image-text alignment (torchmetrics)
      2. Qwen2.5-VL-7B-Instruct — semantic prompt alignment + educational usefulness
    """

    @modal.enter()
    def load_models(self) -> None:
        import torch
        from torchmetrics.multimodal.clip_score import CLIPScore
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        # ── CLIPScore ────────────────────────────────────────────────────────
        # Loaded onto GPU; pre-warmed so the first request is fast
        self.clip_metric = CLIPScore(
            model_name_or_path=CLIP_MODEL_ID
        ).to("cuda")

        # ── Qwen2.5-VL-7B ────────────────────────────────────────────────────
        self.vlm_processor = AutoProcessor.from_pretrained(
            VLM_CACHE_PATH,
            trust_remote_code=True,
        )
        self.vlm_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            VLM_CACHE_PATH,
            torch_dtype=torch.float16,
            device_map="cuda",
            trust_remote_code=True,
        )
        self.vlm_model.eval()

        from shared.memory import MemoryManager

        memory = MemoryManager(
            agent_name="eval-agent",
            skill_path=Path(AGENT_CONFIG_PATH) / "SKILL.md",
            memento_path=Path(AGENT_CONFIG_PATH) / "MEMENTO.md",
        )
        self.agent_context = memory.load_static_context()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_clip_score(self, image_bytes: bytes, prompt: str) -> float:
        """
        Compute CLIPScore for image-text alignment.

        DTYPE GUARD (Flag 6 from review):
          torchmetrics CLIPScore requires uint8 tensor of shape (3, H, W).
          Using float32 or normalized values silently returns NaN or 1.0.
          We convert PIL → numpy → explicit uint8 tensor → permute to (C,H,W).

        STATE RESET GUARD:
          torchmetrics Metric objects accumulate internal states across update/forward calls.
          We call self.clip_metric.reset() after computing to prevent memory leaks and score
          averaging across unrelated requests.
        """
        import numpy as np
        import torch
        from PIL import Image

        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(pil_img)                           # (H, W, 3), dtype uint8
        tensor = torch.tensor(arr, dtype=torch.uint8)     # explicit uint8 cast
        tensor = tensor.permute(2, 0, 1).unsqueeze(0)     # (1, 3, H, W)

        try:
            with torch.no_grad():
                score = self.clip_metric(tensor.to("cuda"), [prompt])
            val = float(score.item())
        finally:
            self.clip_metric.reset()

        return val

    def _vlm_infer(self, prompt: str) -> str:
        """Run a single Qwen2.5-VL text-only inference call (used for JSON correction retries)."""
        import torch
        # NOTE: process_vision_info is NOT imported here — this is a text-only call.
        # The VL processor accepts images=None for text-only inference.

        messages = [{"role": "user", "content": prompt}]
        text = self.vlm_processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.vlm_processor(
            text=[text],
            images=None,           # ← explicit: no image on this correction path
            return_tensors="pt",
        ).to("cuda")

        with torch.no_grad():
            output_ids = self.vlm_model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=True,
            )

        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        return self.vlm_processor.decode(new_tokens, skip_special_tokens=True)

    def _vlm_eval_with_image(self, image_bytes: bytes, prompt: str) -> str:
        """
        Run Qwen2.5-VL inference with both text AND image.

        IMAGE PAYLOAD GUARD (Flag 3 from review):
          The image is passed as a base64 data URI in the image_url content block.
          This is the correct format for Qwen2.5-VL via transformers when images
          are not local files. The data URI is constructed explicitly here — it is
          NOT assumed to work automatically.
        """
        import torch
        from qwen_vl_utils import process_vision_info

        # Explicit base64 encoding — verified non-empty by the caller
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64}"

        from shared.token_budget import TokenBudgetController

        instructions = TokenBudgetController().assemble("eval_agent", {
            "system": "You are evaluating an AI-generated educational image.",
            "skill_rules": self.agent_context["skill_rules"],
            "memento": self.agent_context["memento"],
            "generation_prompt": f'The image was generated from this prompt:\n"{prompt}"',
            "output_schema": (
                "Return prompt_alignment and educational_usefulness scores from 0 to 10, "
                "plus one sentence of actionable feedback."
            ),
        })

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"{instructions}\n\n"
                            "Evaluate the image on two dimensions and respond with ONLY a JSON object:\n"
                            "{\n"
                            '  "prompt_alignment": <float 0-10>,\n'
                            '  "educational_usefulness": <float 0-10>,\n'
                            '  "feedback": "<one sentence explaining scores>"\n'
                            "}\n\n"
                            "No prose. No markdown. No code fences."
                        ),
                    },
                ],
            }
        ]

        text = self.vlm_processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        image_inputs, _ = process_vision_info(messages)
        inputs = self.vlm_processor(
            text=[text],
            images=image_inputs,
            return_tensors="pt",
        ).to("cuda")

        with torch.no_grad():
            output_ids = self.vlm_model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.1,
                do_sample=True,
            )

        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        return self.vlm_processor.decode(new_tokens, skip_special_tokens=True)

    # ── Public Modal method ───────────────────────────────────────────────────

    @modal.method()
    def evaluate(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Evaluate image quality via CLIPScore and Qwen2.5-VL.

        Input:  {"image_bytes": bytes,
                 "enhanced_prompt": str | None,
                 "raw_prompt": str}
        Output: {"clip_score": float | None,
                 "vlm_score": float | None,
                 "visual_score": float | None,
                 "pedagogical_score": float | None,
                 "vlm_feedback": str | None,
                 "error": str | None}

        Contract:
          - image_bytes must be non-empty bytes. Returns error dict immediately
            if this guard fails — does NOT silently compute a fake score.
          - VLM JSON parse failures use the shared retry helper; on exhaustion,
            scores default to None with a descriptive error string.
          - Never raises.
        """
        from shared.json_utils import parse_json_with_retry

        # ── IMAGE BYTES GUARD (Flag 3) ────────────────────────────────────────
        image_bytes = state_dict.get("image_bytes")
        if not isinstance(image_bytes, bytes) or len(image_bytes) == 0:
            return {
                "clip_score": None,
                "vlm_score": None,
                "visual_score": None,
                "pedagogical_score": None,
                "vlm_feedback": None,
                "error": (
                    "EvalAgent received empty or non-bytes image_bytes. "
                    "This is a pipeline bug — image-agent may have failed silently."
                ),
            }

        prompt = (
            state_dict.get("enhanced_prompt")
            or state_dict.get("raw_prompt")
            or ""
        ).strip()

        errors: list[str] = []

        # ── CLIPScore ─────────────────────────────────────────────────────────
        clip_score: float | None = None
        try:
            clip_score = self._compute_clip_score(image_bytes, prompt)
        except Exception as exc:
            errors.append(f"CLIPScore failed: {exc}")

        # ── VLM evaluation ────────────────────────────────────────────────────
        vlm_score: float | None = None
        visual_score: float | None = None
        pedagogical_score: float | None = None
        vlm_feedback: str | None = None
        try:
            raw_vlm_output = self._vlm_eval_with_image(image_bytes, prompt)
            parsed, had_error = parse_json_with_retry(
                raw_output=raw_vlm_output,
                llm_fn=self._vlm_infer,
                correction_prompt=(
                    f"Evaluate this image for educational quality. "
                    f"The generation prompt was: {prompt}"
                ),
                max_retries=MAX_JSON_RETRIES,
            )

            if had_error or parsed is None:
                errors.append("VLM JSON parsing exhausted retries — scores unavailable")
            else:
                pa = parsed.get("prompt_alignment")
                eu = parsed.get("educational_usefulness")
                if pa is not None and eu is not None:
                    visual_score = round(max(0.0, min(10.0, float(pa))), 2)
                    pedagogical_score = round(max(0.0, min(10.0, float(eu))), 2)
                    # Keep the legacy aggregate during the API transition.
                    vlm_score = round((visual_score + pedagogical_score) / 2, 2)
                vlm_feedback = parsed.get("feedback") or "No feedback returned"

        except Exception as exc:
            errors.append(f"VLM evaluation failed: {exc}")

        return {
            "clip_score": clip_score,
            "vlm_score": vlm_score,
            "visual_score": visual_score,
            "pedagogical_score": pedagogical_score,
            "vlm_feedback": vlm_feedback,
            "error": "; ".join(errors) if errors else None,
        }


# ── FastAPI web app ───────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

web_app = FastAPI(
    title="Evaluation Agent",
    description="Evaluates generated images via Qwen2.5-VL-7B and CLIPScore",
    version="1.0.0",
)


class EvalRequest(BaseModel):
    image_base64: str          # base64-encoded PNG from image-agent
    enhanced_prompt: str | None = None
    raw_prompt: str


@web_app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "models": [VLM_MODEL_ID, CLIP_MODEL_ID],
    }


@web_app.post("/evaluate")
def evaluate(req: EvalRequest) -> dict:
    """
    Accepts base64-encoded image + prompt; returns eval scores.
    The orchestrator passes image_bytes (raw bytes) internally; this
    endpoint decodes the base64 so HTTP transport stays JSON-safe.
    """
    try:
        # Decode base64 → bytes; validate non-empty before calling agent
        image_bytes = base64.b64decode(req.image_base64)
        if not image_bytes:
            raise HTTPException(
                status_code=422,
                detail={"error": "InvalidPayload", "detail": "image_base64 decoded to empty bytes"},
            )

        agent = EvalAgent()
        result = agent.evaluate.remote({
            "image_bytes": image_bytes,
            "enhanced_prompt": req.enhanced_prompt,
            "raw_prompt": req.raw_prompt,
        })
        return result

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "EvaluationFailed", "detail": str(exc)},
        )


@app.function(image=image)
@modal.asgi_app()
def api() -> FastAPI:
    return web_app
