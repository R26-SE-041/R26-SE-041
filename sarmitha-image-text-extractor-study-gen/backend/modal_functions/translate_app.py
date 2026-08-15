import modal
import torch

MODEL_ID = "facebook/nllb-200-distilled-600M"

def download_model():
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL_ID)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.0",
        "transformers==4.46.3",
        "accelerate>=0.26.0",
        "sentencepiece",
        "huggingface_hub",
        "hf-transfer",
        "fastapi"
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_function(download_model)
)

app = modal.App("sinhala-translation-service", image=image)

@app.cls(
    image=image,
    gpu="T4", # T4 is plenty for 600M model
    timeout=600,
    scaledown_window=600, # scales to 0 after 10 mins idle
)
class TranslateNLLBService:
    @modal.enter()
    def load_model(self):
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load NLLB-200 tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, src_lang="sin_Sinh")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_ID, 
            torch_dtype=torch.float16,
            device_map=self.device
        )

    @modal.fastapi_endpoint(method="POST")
    def translate_text(self, item: dict):
        """
        Accepts JSON: {"text": "<Sinhala text>", "target_language": "ta" | "en"}
        Returns JSON: {"translated_text": "<Translated text>"}
        """
        text = item.get("text", "")
        if not text.strip():
            return {"translated_text": ""}

        target_code = item.get("target_language", "en")
        tgt_lang = "tam_Taml" if target_code == "ta" else "eng_Latn"

        # Tokenize the input text
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        # Generate translation
        with torch.no_grad():
            translated_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(tgt_lang),
                max_length=1024,
                num_beams=4, # Use beam search for better translation quality
                early_stopping=True
            )
        
        # Decode the tokens to text
        translated_text = self.tokenizer.decode(translated_tokens[0], skip_special_tokens=True)

        return {"translated_text": translated_text.strip()}
