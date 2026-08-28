"""Dedicated base/V2 answer endpoints for the hybrid router.

Deploy only after local tests pass:
    modal deploy backend/modal_endpoints/gemma_answer_generator.py

Set MODAL_BASE_GEMMA_URL to the BaseGemmaAnswer ``/generate`` URL and
MODAL_FINETUNED_GEMMA_V2_URL to the FineTunedGemmaV2Answer ``/generate`` URL.
The two classes deliberately load different model stacks; the base class never
imports PEFT or mounts the adapter.
"""

from __future__ import annotations

import os
from typing import Any

import modal
from pydantic import BaseModel, Field

_BASE_MODEL_ID = "google/gemma-4-12B-it"
_ADAPTER_PATH = "/models/gemma/adapters/v2"
_APP_NAME = "voicelearn-hybrid-gemma"

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "transformers>=5.0.0", "torch>=2.4.0", "accelerate>=0.28.0",
    "torchvision>=0.19.0", "pillow>=10.0.0", "peft==0.20.0",
    "fastapi[standard]>=0.115.0", "pydantic>=2.0.0",
)
app = modal.App(_APP_NAME, image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)


class AnswerRequest(BaseModel):
    query: str
    context: list[str] = Field(default_factory=list)
    language: str = "english"
    tutor_instructions: str = ""
    memento: dict[str, Any] | None = None
    route: str


def _messages(payload: AnswerRequest, *, document_only: bool) -> list[dict[str, str]]:
    language_note = {
        "tamil": "Answer in Tamil Unicode script.",
        "sinhala": "Answer in Sinhala Unicode script.",
    }.get(payload.language.lower(), "Answer in English.")
    policy = payload.tutor_instructions.strip()
    memory = payload.memento or {}
    memory_text = "\n".join(
        f"- {key}: {memory[key]}" for key in (
            "topic", "previous_question", "previous_answer_summary"
        ) if memory.get(key)
    )
    if document_only:
        context = "\n\n---\n\n".join(payload.context)
        system = (
            "You are an academic tutor. Use ONLY the supplied retrieved document "
            "context as factual evidence. If it lacks the answer, say so. " + language_note
        )
        user = f"Retrieved document context:\n{context}\n\nQuestion: {payload.query}"
    else:
        system = "You are a helpful academic tutor. " + language_note
        user = f"Question: {payload.query}"
    if policy:
        system += "\n\nTutor guidance:\n" + policy
    if memory_text:
        user = "Temporary follow-up context:\n" + memory_text + "\n\n" + user
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class _GemmaAnswerBase:
    def _generate(self, payload: AnswerRequest, *, document_only: bool) -> dict[str, str]:
        import torch

        messages = _messages(payload, document_only=document_only)
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt", enable_thinking=False,
        ).to(self.model.device)
        input_length = inputs["input_ids"].shape[-1]
        with torch.inference_mode():
            output = self.model.generate(
                **inputs, max_new_tokens=900, do_sample=False,
                pad_token_id=self.processor.tokenizer.eos_token_id,
            )
        return {
            "answer": self.processor.decode(output[0][input_length:], skip_special_tokens=True).strip(),
            "route": payload.route,
            "model_id": _BASE_MODEL_ID,
            "adapter_active": bool(getattr(self.model, "peft_config", None)),
        }


@app.cls(gpu="A100-80GB", volumes={"/models": model_volume}, min_containers=0,
         max_containers=1, buffer_containers=0, scaledown_window=60, memory=16384)
class BaseGemmaAnswer(_GemmaAnswerBase):
    """Base Gemma only; used for both document RAG and general questions."""

    @modal.enter()
    def load_model(self):
        import torch
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        self.processor = AutoProcessor.from_pretrained(_BASE_MODEL_ID, cache_dir="/models", local_files_only=True)
        self.model = AutoModelForMultimodalLM.from_pretrained(
            _BASE_MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto",
            attn_implementation="sdpa", cache_dir="/models", local_files_only=True,
        ).eval()
        if getattr(self.model, "peft_config", None):
            raise RuntimeError("Base Gemma isolation failed: PEFT configuration is present")
        print(
            "[BaseGemmaAnswer] READY "
            f"base={_BASE_MODEL_ID}; model_class={type(self.model).__name__}; "
            "adapter_active=false; peft_wrapper=false; local_files_only=true"
        )

    @modal.fastapi_endpoint(method="GET")
    def health(self):
        return {
            "ready": True,
            "model_id": _BASE_MODEL_ID,
            "adapter_active": False,
            "peft_wrapper": False,
        }

    @modal.fastapi_endpoint(method="POST")
    def generate(self, payload: AnswerRequest):
        if payload.route not in {"document_rag_base", "general_base"}:
            raise ValueError("Base endpoint received an invalid route")
        document_only = payload.route == "document_rag_base"
        if document_only and not payload.context:
            raise ValueError("Document route requires retrieved context")
        print(f"[BaseGemmaAnswer] route={payload.route}; context_chunks={len(payload.context)}")
        return self._generate(payload, document_only=document_only)


@app.cls(gpu="A100-80GB", volumes={"/models": model_volume}, min_containers=0,
         max_containers=1, buffer_containers=0, scaledown_window=60, memory=16384)
class FineTunedGemmaV2Answer(_GemmaAnswerBase):
    """Gemma plus the verified VoiceLearn V2 LoRA; never accepts RAG context."""

    @modal.enter()
    def load_model(self):
        import json
        import torch
        from peft import PeftModel
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        adapter_config_path = os.path.join(_ADAPTER_PATH, "adapter_config.json")
        if not os.path.isfile(adapter_config_path):
            raise FileNotFoundError("VoiceLearn V2 adapter config is missing")
        with open(adapter_config_path, "r", encoding="utf-8") as handle:
            adapter_config = json.load(handle)
        if adapter_config.get("base_model_name_or_path") != _BASE_MODEL_ID:
            raise RuntimeError("VoiceLearn V2 adapter declares the wrong base model")
        if str(adapter_config.get("peft_type", "")).upper() != "LORA":
            raise RuntimeError("VoiceLearn V2 adapter is not PEFT LoRA")
        self.processor = AutoProcessor.from_pretrained(_ADAPTER_PATH, cache_dir="/models", local_files_only=True)
        base = AutoModelForMultimodalLM.from_pretrained(
            _BASE_MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto",
            attn_implementation="sdpa", cache_dir="/models", local_files_only=True,
        )
        self.model = PeftModel.from_pretrained(base, _ADAPTER_PATH, local_files_only=True).eval()
        if not getattr(self.model, "peft_config", None):
            raise RuntimeError("VoiceLearn V2 PEFT adapter did not activate")
        print(
            "[FineTunedGemmaV2Answer] READY "
            f"base={_BASE_MODEL_ID}; adapter={_ADAPTER_PATH}; PEFT=LORA; "
            f"adapters={list(self.model.peft_config)}; local_files_only=true"
        )

    @modal.fastapi_endpoint(method="GET")
    def health(self):
        return {
            "ready": True,
            "model_id": _BASE_MODEL_ID,
            "adapter_path": _ADAPTER_PATH,
            "adapter_active": bool(getattr(self.model, "peft_config", None)),
            "peft_type": "LORA",
        }

    @modal.fastapi_endpoint(method="POST")
    def generate(self, payload: AnswerRequest):
        if payload.route != "muscle_finetuned_v2" or payload.context:
            raise ValueError("V2 endpoint only accepts non-RAG five-muscle questions")
        print(f"[FineTunedGemmaV2Answer] route={payload.route}; context_chunks=0")
        return self._generate(payload, document_only=False)
