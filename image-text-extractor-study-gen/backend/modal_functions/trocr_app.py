"""
TrOCR OCR — Modal Serverless Function

Uses microsoft/trocr-large-handwritten (per SRCNN skill spec — handwritten images).

Workflow:
  1. Receive enhanced image bytes (base64) via POST
  2. Run TrOCR processor + VisionEncoderDecoderModel
  3. Return extracted text

Deploy:
  modal deploy modal_functions/trocr_app.py
"""

import io
import modal

# ---------------------------------------------------------------------------
# Container image — HuggingFace model baked in at build time
# ---------------------------------------------------------------------------
HF_MODEL = "microsoft/trocr-large-handwritten"
HF_CACHE = "/hf_cache"  # baked into the Modal image

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.3.1",
        "torchvision==0.18.1",
        "transformers==4.41.2",
        "pillow==10.3.0",
        "sentencepiece==0.2.0",
        "accelerate==0.30.1",   # faster model loading
        "fastapi[standard]",
    )
    .env({"HF_HOME": HF_CACHE, "TRANSFORMERS_OFFLINE": "0"})
    .run_commands(
        # Pre-download model at build time → zero cold-start HF network calls
        f"python -c \""
        "import os; os.environ['HF_HOME'] = '/hf_cache'; "
        "from transformers import TrOCRProcessor, VisionEncoderDecoderModel; "
        f"TrOCRProcessor.from_pretrained('{HF_MODEL}'); "
        f"VisionEncoderDecoderModel.from_pretrained('{HF_MODEL}'); "
        "print('TrOCR model cached successfully')"
        "\""
    )
)

app = modal.App("trocr-ocr-service", image=image)


# ---------------------------------------------------------------------------
# Modal class — model loaded once per container
# ---------------------------------------------------------------------------
@app.cls(gpu="T4", scaledown_window=60)
class TrOCRExtractor:
    @modal.enter()
    def load_model(self):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # local_files_only=True → use the weights baked into the image, no network calls
        self.processor = TrOCRProcessor.from_pretrained(
            HF_MODEL, local_files_only=True
        )
        self.model = VisionEncoderDecoderModel.from_pretrained(
            HF_MODEL, local_files_only=True
        ).to(self.device)
        self.model.eval()
        print(f"[TrOCR] Model loaded on {self.device}")

    @modal.fastapi_endpoint(method="POST")
    def extract_text(self, request: dict) -> dict:
        """
        Accepts JSON: {"image_b64": "<base64-encoded image>"}
        Returns JSON: {"text": "...", "confidence": null}
        """
        import base64
        import torch
        from PIL import Image

        # Decode image
        image_bytes = base64.b64decode(request["image_b64"])
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # TrOCR processing
        pixel_values = self.processor(
            images=img, return_tensors="pt"
        ).pixel_values.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(
                pixel_values,
                max_new_tokens=512,
            )

        text = self.processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]

        return {"text": text.strip()}
