import os
import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.5.3.post1",
        "huggingface_hub",
        "hf-transfer",
        "fastapi",
        "pillow"
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": "/hf_cache"})
    .run_commands(
        "hf download Qwen/Qwen2-VL-7B-Instruct"
    )
)

app = modal.App("sinhala-visual-ocr-verification-service", image=image)

@app.cls(
    image=image,
    gpu="A10G",
    timeout=600,
    scaledown_window=600,  # scales to 0 after 10 mins idle
)
class VisualOCRVerifier:
    @modal.enter()
    def load_model(self):
        from vllm import LLM
        self.llm = LLM(
            model="Qwen/Qwen2-VL-7B-Instruct",
            tensor_parallel_size=1,
            gpu_memory_utilization=0.90,
            max_model_len=4096,
        )
        
    @modal.fastapi_endpoint(method="POST")
    def verify_text(self, item: dict):
        raw_text = item.get("text", "")
        base64_image = item.get("image_b64", "")
        
        if not base64_image:
            return {"verified_text": raw_text}

        from vllm import SamplingParams
        sampling_params = SamplingParams(
            temperature=0.1,
            max_tokens=2048,
        )

        # Qwen2-VL specific prompt formatting
        prompt = "Extract the handwritten Sinhala text from this image exactly as written. Return ONLY the correct Sinhala text without any translation, formatting, or conversational filler."
        if raw_text:
             prompt = f"Extract the handwritten Sinhala text from this image exactly as written. The initial OCR extraction was '{raw_text}'. Fix any visible structural errors and return ONLY the correct Sinhala text."
             
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        
        # vLLM automatically handles the chat template for vision models
        outputs = self.llm.chat(messages, sampling_params)
        generated_text = outputs[0].outputs[0].text.strip()

        return {"verified_text": generated_text}
