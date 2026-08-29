"""Modal GPU endpoint for Qwen2.5-7B with the Nishy LoRA adapter.

Deploy from the backend directory:
    modal deploy modal_inference/qwen_endpoint.py

Required Modal secret:
    modal secret create huggingface-secret HF_TOKEN=hf_your_token_here
"""

import modal

BASE_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
LORA_ADAPTER_ID = "Nishy11/nishy-qwen2.5-7b-v4"
GPU_TYPE = "A10G"

hf_secret = modal.Secret.from_name("huggingface-secret")


def download_models():
    """Cache the base model and adapter in the Modal image."""
    import os
    from huggingface_hub import snapshot_download

    token = os.environ.get("HF_TOKEN")
    snapshot_download(
        repo_id=BASE_MODEL_ID,
        token=token,
        ignore_patterns=["*.pt", "*.bin"],
    )
    snapshot_download(
        repo_id=LORA_ADAPTER_ID,
        token=token,
        ignore_patterns=["*.pt", "*.bin"],
    )


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.5.1",
        "transformers==4.57.6",
        "peft==0.20.0",
        "accelerate==1.14.0",
        "huggingface_hub==0.36.2",
        "hf-transfer==0.1.8",
        "fastapi",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_function(download_models, secrets=[hf_secret])
)

app = modal.App("nishy-qwen-adaptive-quiz", image=image)


@app.cls(
    gpu=GPU_TYPE,
    timeout=600,
    scaledown_window=600,
    secrets=[hf_secret],
)
@modal.concurrent(max_inputs=1)
class QwenModel:
    @modal.enter()
    def load_model(self):
        """Load the base model and attach the LoRA adapter once per container."""
        import os
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        token = os.environ.get("HF_TOKEN")
        self.tokenizer = AutoTokenizer.from_pretrained(
            BASE_MODEL_ID,
            trust_remote_code=True,
            token=token,
        )
        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="cuda",
            trust_remote_code=True,
            token=token,
        )
        self.model = PeftModel.from_pretrained(
            base_model,
            LORA_ADAPTER_ID,
            token=token,
        )
        self.model.eval()
        print(f"READY: {BASE_MODEL_ID} + {LORA_ADAPTER_ID} loaded on {GPU_TYPE}")

    @modal.method()
    def generate(
        self,
        prompt: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response with the fine-tuned model."""
        import torch

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert educational assessment AI. Follow "
                    "instructions precisely and return only valid JSON when asked."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        formatted = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(formatted, return_tensors="pt").to("cuda")
        generation_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            generation_kwargs["temperature"] = temperature

        with torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generation_kwargs)

        new_tokens = output_ids[0, inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


@app.function(timeout=600)
@modal.concurrent(max_inputs=10)
@modal.asgi_app()
def web_endpoint():
    """Expose the model through a small HTTP API."""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    api = FastAPI(title="Nishy Qwen2.5-7B Fine-Tuned Inference API")
    model = QwenModel()

    class GenerateRequest(BaseModel):
        prompt: str
        temperature: float = 0.4
        max_new_tokens: int = 1024

    class GenerateResponse(BaseModel):
        response: str
        model: str = LORA_ADAPTER_ID

    @api.post("/generate", response_model=GenerateResponse)
    def generate(req: GenerateRequest):
        try:
            text = model.generate.remote(
                req.prompt,
                temperature=req.temperature,
                max_tokens=req.max_new_tokens,
            )
            return GenerateResponse(response=text)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @api.get("/health")
    def health():
        return {
            "status": "ok",
            "base_model": BASE_MODEL_ID,
            "adapter": LORA_ADAPTER_ID,
        }

    return api


@app.local_entrypoint()
def test_generate():
    model = QwenModel()
    result = model.generate.remote(
        prompt='Return only JSON: {"answer": "Hello from Qwen!"}',
        temperature=0.1,
        max_tokens=128,
    )
    print("Test output:", result)
