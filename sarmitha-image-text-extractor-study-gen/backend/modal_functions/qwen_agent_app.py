"""
Sinhala OCR Validation Agent — Modal Serverless Function
Model: Qwen/Qwen2.5-7B-Instruct
Uses vLLM for fast inference.
"""

import modal

HF_MODEL = "Qwen/Qwen2.5-7B-Instruct"
HF_CACHE = "/hf_cache"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.5.4",
        "transformers==4.46.3",
        "fastapi[standard]",
        "hf_transfer==0.1.6"
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": HF_CACHE, "VLLM_NO_USAGE_STATS": "1"})
    # Pre-download model weights during image build for faster cold starts
    .run_commands(
        f"python -c 'import huggingface_hub; huggingface_hub.snapshot_download(\"{HF_MODEL}\", max_workers=8)'"
    )
)

app = modal.App("sinhala-qwen-ocr-validation-service")

with image.imports():
    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer

@app.cls(
    image=image,
    gpu="A10G",
    timeout=600,
    scaledown_window=600,  # 10 mins warm state
)
class QwenOCRValidator:
    @modal.enter()
    def load_model(self):
        print(f"Loading {HF_MODEL} into vLLM...")
        self.llm = LLM(
            model=HF_MODEL,
            dtype="bfloat16",
            gpu_memory_utilization=0.90,
            max_model_len=4096,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(HF_MODEL)
        
        # We need conservative sampling to prevent hallucination
        self.sampling_params = SamplingParams(
            temperature=0.1,  # highly deterministic
            top_p=0.95,
            max_tokens=1024,
            repetition_penalty=1.05,
        )
        print("Model loaded successfully.")

    @modal.fastapi_endpoint(method="POST")
    def validate_ocr(self, request: dict) -> dict:
        """
        Accepts JSON: {"raw_text": "..."}
        Returns JSON: {"validated_text": "..."}
        """
        raw_text = request.get("raw_text", "").strip()
        if not raw_text:
            return {"validated_text": ""}

        system_prompt = (
            "You are a strict Sinhala OCR Validation Agent. Your task is to fix minor spelling and grammatical "
            "errors in raw Sinhala OCR text extracted from handwritten notes.\n\n"
            "CRITICAL RULES:\n"
            "1. ONLY output the corrected Sinhala text. Do NOT add ANY conversational filler (e.g. 'Here is the text').\n"
            "2. Make CONSERVATIVE corrections. Fix obvious misspellings, but DO NOT rewrite or translate the text.\n"
            "3. DO NOT invent or add new information that is not present in the original text.\n"
            "4. Preserve the original formatting (newlines) as much as possible."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Correct this raw Sinhala OCR text:\n\n{raw_text}"}
        ]

        prompt = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )

        outputs = self.llm.generate([prompt], self.sampling_params)
        generated_text = outputs[0].outputs[0].text.strip()

        return {"validated_text": generated_text}
