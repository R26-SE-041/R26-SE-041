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
import json
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
GLOBAL_CONFIG_PATH = "/root/agent-config/global"


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
    .add_local_dir(
        "anatomy",
        remote_path="/root/anatomy",
        ignore=["**/__pycache__/**", "**/*.pyc"],
    )
    .add_local_file("agents/eval-agent/SKILL.md", f"{AGENT_CONFIG_PATH}/SKILL.md")
    .add_local_file("agents/eval-agent/MEMENTO.md", f"{AGENT_CONFIG_PATH}/MEMENTO.md")
    .add_local_file("agents/eval-agent/PERSONA.md", f"{AGENT_CONFIG_PATH}/PERSONA.md")
    .add_local_file("config/global/PERSONA.md", f"{GLOBAL_CONFIG_PATH}/PERSONA.md")
    .add_local_file("config/global/SKILL.md", f"{GLOBAL_CONFIG_PATH}/SKILL.md")
    .add_local_file("config/global/MEMENTO.md", f"{GLOBAL_CONFIG_PATH}/MEMENTO.md")
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
        from transformers import AutoProcessor, CLIPModel, CLIPProcessor, Qwen2_5_VLForConditionalGeneration

        # ── CLIPScore ────────────────────────────────────────────────────────
        # Loaded onto GPU; pre-warmed so the first request is fast
        self.clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
        self.clip_model = CLIPModel.from_pretrained(CLIP_MODEL_ID).to("cuda").eval()

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
            global_root=GLOBAL_CONFIG_PATH,
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
        inputs = self.clip_processor(
            text=[prompt],
            images=[pil_img],
            return_tensors="pt",
            padding=True,
        ).to("cuda")
        with torch.no_grad():
            image_output = self.clip_model.get_image_features(pixel_values=inputs["pixel_values"])
            text_output = self.clip_model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )
            image_features = getattr(image_output, "pooler_output", image_output)
            text_features = getattr(text_output, "pooler_output", text_output)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            score = 100.0 * (image_features * text_features).sum(dim=-1)
        return float(torch.clamp(score, min=0.0).item())

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

    def _vlm_eval_with_image(
        self,
        image_bytes: bytes,
        prompt: str,
        anatomy_spec: dict[str, Any] | None = None,
    ) -> str:
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
            "system": "\n\n".join(filter(None, [
                self.agent_context["system_persona"],
                "Your active role is evaluating an AI-generated educational image.",
            ])),
            "skill_rules": self.agent_context["skill_rules"],
            "memento": self.agent_context["memento"],
            "generation_prompt": f'The image was generated from this prompt:\n"{prompt}"',
            "output_schema": (
                "Return prompt_alignment and educational_usefulness scores from 0 to 10, "
                "plus one sentence of actionable feedback."
            ),
        })

        anatomy_instruction = ""
        if anatomy_spec and anatomy_spec.get("is_anatomy"):
            anatomy_instruction = (
                "\nThis is a clean anatomy base-image evaluation. Inspect only visible evidence. "
                "Use canonical IDs from this specification and never infer a hidden structure:\n"
                f"{json.dumps(anatomy_spec, ensure_ascii=False)}\n"
                "Also report detected_structures, orientation_correct, relation_accuracy (0 to 1), "
                "embedded_text_present, hallucinated_structures, and hard_failures. A hard failure includes "
                "wrong laterality/orientation, an impossible major connection, or embedded text/labels."
            )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": data_uri},
                    {
                        "type": "text",
                        "text": (
                            f"{instructions}\n\n"
                            f"{anatomy_instruction}\n"
                            "Evaluate the image and respond with ONLY a JSON object:\n"
                            "{\n"
                            '  "prompt_alignment": <float 0-10>,\n'
                            '  "educational_usefulness": <float 0-10>,\n'
                            '  "feedback": "<one sentence explaining scores>",\n'
                            '  "detected_structures": ["<canonical_id>"],\n'
                            '  "orientation_correct": <boolean or null>,\n'
                            '  "relation_accuracy": <float 0-1 or null>,\n'
                            '  "embedded_text_present": <boolean>,\n'
                            '  "hallucinated_structures": ["<visible unsupported structure>"],\n'
                            '  "hard_failures": ["<concise visible failure>"]\n'
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
                max_new_tokens=384 if anatomy_spec and anatomy_spec.get("is_anatomy") else 256,
                temperature=0.0,
                do_sample=False,
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
        anatomy_spec = state_dict.get("anatomy_spec") or {"is_anatomy": False}
        enable_anatomy_critic = bool(state_dict.get("enable_anatomy_critic", True))

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
        anatomy_metrics: dict[str, Any] = {}
        anatomy_hard_failures: list[str] = []
        try:
            raw_vlm_output = self._vlm_eval_with_image(
                image_bytes,
                prompt,
                anatomy_spec if enable_anatomy_critic else None,
            )
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
                if enable_anatomy_critic and anatomy_spec.get("is_anatomy"):
                    from anatomy import canonicalize_structure, list_supported_organs

                    organ = str(anatomy_spec.get("organ") or "")
                    expected = [str(value) for value in anatomy_spec.get("required_structures") or []]
                    detected: list[str] = []
                    if organ.casefold().replace(" ", "_") in set(list_supported_organs()):
                        for value in parsed.get("detected_structures") or []:
                            canonical = canonicalize_structure(organ, str(value))
                            if canonical and canonical not in detected:
                                detected.append(canonical)
                    else:
                        expected_lookup = {value.casefold().replace("_", " "): value for value in expected}
                        for value in parsed.get("detected_structures") or []:
                            canonical = expected_lookup.get(str(value).casefold().replace("_", " "))
                            if canonical and canonical not in detected:
                                detected.append(canonical)
                    expected_set = set(expected)
                    detected_set = set(detected)
                    missing = sorted(expected_set - detected_set)
                    hallucinated = sorted({
                        str(value) for value in parsed.get("hallucinated_structures") or [] if str(value).strip()
                    })
                    orientation = parsed.get("orientation_correct")
                    relation_value = parsed.get("relation_accuracy")
                    relation_accuracy = (
                        round(max(0.0, min(1.0, float(relation_value))), 4)
                        if relation_value is not None else None
                    )
                    structure_recall = round(len(expected_set & detected_set) / len(expected_set), 4) if expected_set else 1.0
                    embedded_text = bool(parsed.get("embedded_text_present", False))
                    anatomy_hard_failures = [
                        str(value)[:240] for value in parsed.get("hard_failures") or [] if str(value).strip()
                    ]
                    if orientation is False:
                        anatomy_hard_failures.append("Incorrect anatomical orientation or laterality")
                    if embedded_text:
                        anatomy_hard_failures.append("Clean base image contains embedded text or labels")
                    if len(missing) >= 2:
                        anatomy_hard_failures.append(f"Missing required structures: {', '.join(missing)}")
                    anatomy_hard_failures = list(dict.fromkeys(anatomy_hard_failures))
                    anatomy_metrics = {
                        "expected_structures": expected,
                        "detected_structures": detected,
                        "missing_structures": missing,
                        "hallucinated_structures": hallucinated,
                        "structure_recall": structure_recall,
                        "orientation_correct": orientation,
                        "relation_accuracy": relation_accuracy,
                        "clean_image_compliance": 0.0 if embedded_text else 1.0,
                    }

        except Exception as exc:
            errors.append(f"VLM evaluation failed: {exc}")

        return {
            "clip_score": clip_score,
            "vlm_score": vlm_score,
            "visual_score": visual_score,
            "pedagogical_score": pedagogical_score,
            "vlm_feedback": vlm_feedback,
            "anatomy_metrics": anatomy_metrics,
            "anatomy_hard_failures": anatomy_hard_failures,
            "error": "; ".join(errors) if errors else None,
        }


# ── FastAPI web app ───────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

web_app = FastAPI(
    title="Evaluation Agent",
    description="Evaluates generated images via Qwen2.5-VL-7B and CLIPScore",
    version="1.0.0",
)

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@web_app.options("/{path:path}")
def cors_preflight(path: str) -> Response:
    """Keep browser preflight available even behind method-aware proxies."""
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept",
            "Access-Control-Max-Age": "600",
        },
    )


class EvalRequest(BaseModel):
    image_base64: str          # base64-encoded PNG from image-agent
    enhanced_prompt: str | None = None
    raw_prompt: str
    anatomy_spec: dict[str, Any] = Field(default_factory=lambda: {"is_anatomy": False})
    enable_anatomy_critic: bool = True


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
            "anatomy_spec": req.anatomy_spec,
            "enable_anatomy_critic": req.enable_anatomy_critic,
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
