"""
Sinhala Handwritten OCR — Modal Serverless Function

Model: hasindu-k/sinhala-handwritten-notes-v3
  - VisionEncoderDecoderModel fine-tuned for Sinhala handwritten notes (v3)
  - Fine-tuned from eshangj/TrOCR-Sinhala-finetuned
  - ~315M params (F32), Apache-2.0, open-source
  - Files: config.json, model.safetensors, processor_config.json,
           tokenizer.json, tokenizer_config.json
  - Language tag: si (Sinhala)

Loader strategy: use ViTImageProcessor (reads processor_config.json) +
AutoTokenizer to avoid compatibility issues with AutoProcessor.

Warm state: 10 minutes (scaledown_window=600)

Deploy:
  modal deploy modal_functions/trocr_app.py
"""

import io
import modal

HF_MODEL = "hasindu-k/sinhala-handwritten-notes-v3"
HF_CACHE = "/hf_cache"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.3.1",
        "torchvision==0.18.1",
        "transformers==4.30.2",  # pinned: >=4.38 rejects early_stopping:null in config.json
        "pillow==10.3.0",
        "sentencepiece==0.2.0",
        "accelerate==0.30.1",
        "opencv-python-headless==4.10.0.84",
        "fastapi[standard]",
    )
    .env({"HF_HOME": HF_CACHE, "TRANSFORMERS_OFFLINE": "0"})
    .run_commands(
        "python -c 'import os; os.environ[\"HF_HOME\"] = \"/hf_cache\"; from huggingface_hub import snapshot_download; "
        f"snapshot_download(repo_id=\"{HF_MODEL}\"); "
        "print(\"Download complete\")'",
        gpu="T4"
    )
    .run_commands(
        "python -c \"import base64; exec(base64.b64decode('aW1wb3J0IGpzb24sIG9zCmRlZiBmZChkKToKICAgIGlmIGlzaW5zdGFuY2UoZCwgZGljdCk6CiAgICAgICAgaWYgZC5nZXQoImVhcmx5X3N0b3BwaW5nIikgaXMgTm9uZSBhbmQgImVhcmx5X3N0b3BwaW5nIiBpbiBkOiBkWyJlYXJseV9zdG9wcGluZyJdID0gRmFsc2UKICAgICAgICBbZmQodikgZm9yIHYgaW4gZC52YWx1ZXMoKV0KICAgIGVsaWYgaXNpbnN0YW5jZShkLCBsaXN0KTogW2ZkKGkpIGZvciBpIGluIGRdCmZvciBjIGluIFsiL2hmX2NhY2hlIiwgIi9yb290Ly5jYWNoZS9odWdnaW5nZmFjZSJdOgogICAgZm9yIHIsIF8sIGZzIGluIG9zLndhbGsoYyk6CiAgICAgICAgZm9yIGYgaW4gZnM6CiAgICAgICAgICAgIGlmIGYuZW5kc3dpdGgoIi5qc29uIik6CiAgICAgICAgICAgICAgICBwID0gb3MucGF0aC5qb2luKHIsIGYpCiAgICAgICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICAgICAgZCA9IGpzb24ubG9hZChvcGVuKHApKQogICAgICAgICAgICAgICAgICAgIGZkKGQpCiAgICAgICAgICAgICAgICAgICAgb3BlbihwLCAidyIpLndyaXRlKGpzb24uZHVtcHMoZCkpCiAgICAgICAgICAgICAgICAgICAgcHJpbnQoInBhdGNoZWQiLCBwKQogICAgICAgICAgICAgICAgZXhjZXB0OiBwYXNzCg==').decode('utf-8'))\""
    )
    .run_commands(
        "python -c 'import os; os.environ[\"HF_HOME\"] = \"/hf_cache\"; from transformers import ViTImageProcessor, AutoTokenizer, VisionEncoderDecoderModel; "
        f"ViTImageProcessor.from_pretrained(\"{HF_MODEL}\", local_files_only=True); "
        f"AutoTokenizer.from_pretrained(\"{HF_MODEL}\", local_files_only=True); "
        f"VisionEncoderDecoderModel.from_pretrained(\"{HF_MODEL}\", local_files_only=True); "
        "print(\"Sinhala TrOCR model cached successfully\")'"
    )
)

app = modal.App("sinhala-trocr-ocr-service", image=image)  # App name unchanged for endpoint URL stability


@app.cls(gpu="T4", scaledown_window=600)  # 10-minute warm state
class SinhalaTrOCRExtractor:
    @modal.enter()
    def load_model(self):
        import torch
        from transformers import ViTImageProcessor, AutoTokenizer, VisionEncoderDecoderModel

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Explicit class loading — avoids AutoProcessor's image_processor_type requirement
        self.feature_extractor = ViTImageProcessor.from_pretrained(
            HF_MODEL, local_files_only=True
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            HF_MODEL, local_files_only=True
        )
        self.model = VisionEncoderDecoderModel.from_pretrained(
            HF_MODEL, local_files_only=True
        ).to(self.device)

        # Tie decoder output projection to embedding if not already saved in checkpoint.
        # This prevents garbage output from uninitialized lm_head weights.
        output_embeddings = getattr(self.model.decoder, "get_output_embeddings", lambda: None)()
        input_embeddings = getattr(self.model.decoder, "get_input_embeddings", lambda: None)()
        if output_embeddings is not None and input_embeddings is not None:
            output_embeddings.weight = input_embeddings.weight
            print("[TrOCR] Tied decoder output_embeddings to input_embeddings weight")
        elif hasattr(self.model.decoder, "lm_head") and hasattr(self.model.decoder.lm_head, "decoder"):
            self.model.decoder.lm_head.decoder.weight = self.model.decoder.roberta.embeddings.word_embeddings.weight
            print("[TrOCR] Manually tied lm_head decoder to word_embeddings weight")

        # Configure decoder tokens dynamically based on the tokenizer
        self.model.config.decoder_start_token_id = self.tokenizer.cls_token_id if self.tokenizer.cls_token_id is not None else self.tokenizer.bos_token_id
        self.model.config.pad_token_id = self.tokenizer.pad_token_id
        self.model.config.eos_token_id = self.tokenizer.sep_token_id if self.tokenizer.sep_token_id is not None else self.tokenizer.eos_token_id
        
        # Ensure we have a valid EOS token to stop generation hallucinations
        if self.model.config.eos_token_id is None:
            self.model.config.eos_token_id = 2 # Fallback to standard RoBERTa eos

        # Generation parameters optimised for Sinhala handwriting
        self.model.config.max_length = 256
        self.model.config.early_stopping = True
        self.model.config.no_repeat_ngram_size = 0  # Sinhala syllables can repeat
        self.model.config.length_penalty = 1.0
        self.model.config.num_beams = 4

        self.model.eval()
        print(f"[Sinhala TrOCR v3] Model loaded on {self.device}")

    @modal.fastapi_endpoint(method="POST")
    def extract_text(self, request: dict) -> dict:
        """
        Accepts JSON: {"image_b64": "<base64-encoded image>"}
        Returns JSON: {"text": "..."}
        """
        import base64
        import numpy as np
        import cv2
        import torch
        from PIL import Image

        image_bytes = base64.b64decode(request["image_b64"])
        nparr = np.frombuffer(image_bytes, np.uint8)
        cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # OpenCV Preprocessing Pipeline for Noisy/Dark Handwriting
        # 1. Grayscale
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        
        # 2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # This dramatically improves contrast on dark images without blowing out whites.
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(gray)
        
        # 3. Denoise (remove background grain without destroying strokes)
        denoised = cv2.fastNlMeansDenoising(cl, None, h=15, templateWindowSize=7, searchWindowSize=21)
        
        # 4. Unsharp Masking (Sharpen blurry/unclear images)
        gaussian = cv2.GaussianBlur(denoised, (0, 0), 2.0)
        sharpened = cv2.addWeighted(denoised, 1.5, gaussian, -0.5, 0)
        
        # Convert back to PIL RGB
        img_rgb = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
        img_processed = Image.fromarray(img_rgb)

        # OpenCV Line Segmentation for Full-Page Notes
        # TrOCR can only read one line at a time. We slice the paragraph into lines.
        cv_img_rgb = np.array(img_processed)
        cv_img_gray = cv2.cvtColor(cv_img_rgb, cv2.COLOR_RGB2GRAY)
        
        # Binarize to find contours (invert so text is white on black background)
        _, thresh = cv2.threshold(cv_img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Dilate horizontally to connect characters and words into single lines
        # Use dynamic kernel size based on image resolution to prevent chopping words into letters
        img_h, img_w = cv_img_rgb.shape[:2]
        kernel_width = max(40, img_w // 25)
        kernel_height = max(5, img_h // 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, kernel_height))
        dilated = cv2.dilate(thresh, kernel, iterations=2) # 2 iterations for aggressive connection
        
        # Find contours of the lines
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort contours top to bottom (by y coordinate)
        contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[1])
        
        img_area = img_w * img_h
        
        lines = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # Filter out tiny noise contours (smudges) and massive boxes (image borders)
            # For single words, we must accept wider/taller ratios
            if w > max(30, img_w * 0.05) and h > max(20, img_h * 0.02) and (w * h) < (img_area * 0.95):
                # Add vertical padding so we don't cut off tall Sinhala diacritics
                padding = max(10, int(h * 0.15))
                y1 = max(0, y - padding)
                y2 = min(img_h, y + h + padding)
                
                line_crop = cv_img_rgb[y1:y2, x:x+w]
                lines.append(Image.fromarray(line_crop))
        
        # Fallback: if segmentation filtered out everything (e.g. single small word), just read the whole image
        if len(lines) == 0:
            lines = [img_processed]
            
        # Process all lines simultaneously as a GPU batch
        pixel_values = self.feature_extractor(
            images=lines, return_tensors="pt"
        ).pixel_values.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(
                pixel_values,
                max_length=self.model.config.max_length,
                num_beams=self.model.config.num_beams,
                early_stopping=self.model.config.early_stopping,
            )

        texts = self.tokenizer.batch_decode(
            generated_ids, skip_special_tokens=True
        )
        
        # Stitch all lines together separated by newlines
        final_text = "\n".join(texts)

        return {"text": final_text.strip()}
