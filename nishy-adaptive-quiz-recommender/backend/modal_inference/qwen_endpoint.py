"""
Modal.com Serverless Endpoint — Qwen2.5-7B-Instruct
Deploy: modal deploy modal_inference/qwen_endpoint.py
Test:   modal run modal_inference/qwen_endpoint.py::test_generate
"""
import modal

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
GPU_TYPE = "A10G"  # 24GB VRAM — plenty for 7B at 4-bit

def download_model_to_folder():
    from huggingface_hub import snapshot_download
    # Download safetensors, ignore older format weights
    snapshot_download(repo_id=MODEL_ID, ignore_patterns=["*.pt", "*.bin"])

# ── Image: vllm + model cached in container ────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.6.4",
        "huggingface_hub==0.25.2",
        "hf-transfer==0.1.8",
        "fastapi",
        "uvicorn",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_function(download_model_to_folder)
)

app = modal.App("qwen-adaptive-quiz", image=image)

# ── Model class: loaded once, reused across requests ──────────────────────
@app.cls(
    gpu=GPU_TYPE,
    timeout=600,
    scaledown_window=600,   # keep warm for 10 min between requests
)
@modal.concurrent(max_inputs=4)
class QwenModel:
    @modal.enter()
    def load_model(self):
        """Load model on container startup — cached after first cold start."""
        from vllm import LLM, SamplingParams  # noqa: F401
        self.llm = LLM(
            model=MODEL_ID,
            dtype="bfloat16",
            max_model_len=8192,
            gpu_memory_utilization=0.90,
            trust_remote_code=True,
        )
        print(f"✅ Qwen2.5-7B loaded on {GPU_TYPE}")

    @modal.method()
    def generate(
        self,
        prompt: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text from a prompt. Returns raw string."""
        from vllm import SamplingParams

        params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            stop=["<|im_end|>", "<|endoftext|>"],
        )
        # Qwen2.5 chat template
        messages = [
            {"role": "system", "content": "You are an expert educational assessment AI. Follow instructions precisely and return only valid JSON when asked."},
            {"role": "user", "content": prompt},
        ]
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        outputs = self.llm.generate([formatted], params)
        return outputs[0].outputs[0].text.strip()


# ── FastAPI web endpoint ───────────────────────────────────────────────────
@app.function(
    timeout=600,
)
@modal.concurrent(max_inputs=10)
@modal.asgi_app()
def web_endpoint():
    """HTTP endpoint for FastAPI backend to call."""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    api = FastAPI(title="Qwen2.5-7B Inference API")
    model = QwenModel()

    class GenerateRequest(BaseModel):
        prompt: str
        temperature: float = 0.4
        max_tokens: int = 1024

    class GenerateResponse(BaseModel):
        text: str
        model: str = MODEL_ID

    @api.post("/generate", response_model=GenerateResponse)
    def generate(req: GenerateRequest):
        try:
            text = model.generate.remote(
                req.prompt,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            return GenerateResponse(text=text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/health")
    def health():
        return {"status": "ok", "model": MODEL_ID}

    return api


# ── Local test ────────────────────────────────────────────────────────────
@app.local_entrypoint()
def test_generate():
    """Run: modal run modal_inference/qwen_endpoint.py"""
    model = QwenModel()
    result = model.generate.remote(
        prompt='Generate a JSON object with key "answer" and value "Hello from Qwen!"',
        temperature=0.1,
        max_tokens=128,
    )
    print("Test output:", result)
