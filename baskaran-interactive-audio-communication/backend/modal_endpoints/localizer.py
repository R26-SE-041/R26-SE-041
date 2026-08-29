"""
Modal Serverless Endpoint: Qwen2.5-7B — Localization

Deploy:
    modal deploy backend/modal_endpoints/localizer.py

Accepts JSON:
    { "text": str, "language": str }

Returns JSON:
    { "localized_text": str }

Supported languages:
    english  — no-op (returns original)
    tamil    — translate to Tamil script
    sinhala  — translate to Sinhala script
    mixed    — Thanglish (Tamil words in English script) or Singlish
"""

from pydantic import BaseModel
import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers==4.45.0",
        "torch==2.2.0",
        "accelerate==0.28.0",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
    )
)

app = modal.App("voicelearn-localizer", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

class LocalizerRequest(BaseModel):
    text: str
    language: str

LANGUAGE_INSTRUCTIONS = {
    "tamil": (
        "Translate the following academic answer into natural spoken Tamil (தமிழ்). "
        "Keep necessary English technical terms in English and place them naturally "
        "inside Tamil sentences. Preserve their spelling. Use short, complete sentences "
        "that sound clear when read aloud. Do not output Markdown symbols."
    ),
    "sinhala": "Translate the following academic answer to Sinhala (සිංහල). Keep technical terms in English.",
    "mixed": "Rewrite the following in Thanglish (mix of Tamil and English, using English script for Tamil words). Keep it natural and conversational.",
}


@app.cls(
    gpu="T4",
    volumes={"/models": model_volume},
    scaledown_window=300,
    memory=8192,
)
class Localizer:
    @modal.enter()
    def load_model(self):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch

        model_id = "Qwen/Qwen2.5-7B-Instruct"
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir="/models")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            device_map="auto",
            cache_dir="/models",
        )

    @modal.fastapi_endpoint(method="POST")
    async def localize(self, payload: LocalizerRequest):
        import torch

        text: str = payload.text
        language: str = payload.language.lower()

        if language == "english" or language not in LANGUAGE_INSTRUCTIONS:
            return {"localized_text": text}

        instruction = LANGUAGE_INSTRUCTIONS[language]

        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ]

        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")

        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=600,
                temperature=0.3,
                do_sample=True,
            )

        localized = self.tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()

        return {"localized_text": localized or text}
