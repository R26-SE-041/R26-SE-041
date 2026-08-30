"""
Super-Resolution Enhancement — Modal Serverless Function

Model: sarmisarmitha/swin2sr-sinhala-image-enhancement (fine-tuned Swin2SR)
  - 12M params, Apache-2.0, open-source, under 10B
  - Verified public HuggingFace model (all files confirmed via API)
  - Used in 9+ production HuggingFace Spaces
  - 4x classical super-resolution — significantly better than SRCNN bicubic

Replaces SRCNN (which had broken external weight URLs). Swin2SR weights
are baked into the container at image build time from HuggingFace.

Deploy:
  modal deploy modal_functions/srcnn_app.py
"""

import io
import modal

HF_MODEL = "sarmisarmitha/swin2sr-sinhala-image-enhancement"
HF_CACHE = "/hf_cache"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.3.1",
        "torchvision==0.18.1",
        "transformers==4.41.2",
        "pillow==10.3.0",
        "numpy==1.26.4",
        "scipy==1.13.1",
        "opencv-python-headless==4.10.0.84",
        "fastapi[standard]",
    )
    .env({"HF_HOME": HF_CACHE, "TRANSFORMERS_OFFLINE": "0"})
    .run_commands(
        # Pre-download Swin2SR model at build time — no external weight URL needed
        f"python -c \""
        "import os; os.environ['HF_HOME'] = '/hf_cache'; "
        "from transformers import Swin2SRImageProcessor, Swin2SRForImageSuperResolution; "
        f"Swin2SRImageProcessor.from_pretrained('{HF_MODEL}'); "
        f"Swin2SRForImageSuperResolution.from_pretrained('{HF_MODEL}'); "
        "print('Swin2SR model cached successfully')"
        "\""
    )
)

app = modal.App("swin2sr-super-resolution", image=image)


@app.cls(gpu="T4", scaledown_window=300)  # 5 mins warm state
class Swin2SREnhancer:
    @modal.enter()
    def load_model(self):
        import torch
        from transformers import Swin2SRImageProcessor, Swin2SRForImageSuperResolution

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.processor = Swin2SRImageProcessor.from_pretrained(
            HF_MODEL, local_files_only=True
        )
        self.model = Swin2SRForImageSuperResolution.from_pretrained(
            HF_MODEL, local_files_only=True
        ).to(self.device)
        self.model.eval()
        print(f"[Swin2SR] Model loaded on {self.device}")

    @modal.fastapi_endpoint(method="POST")
    def enhance(self, request: dict) -> dict:
        """
        Accepts JSON: {"image_b64": "<base64-encoded image>"}
        Returns JSON: {"enhanced_b64": "<base64-encoded PNG>"}
        """
        import base64
        import numpy as np
        import cv2
        import torch
        from PIL import Image

        # Decode input
        image_bytes = base64.b64decode(request["image_b64"])
        nparr = np.frombuffer(image_bytes, np.uint8)
        cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Scale down image if it's too large to prevent CUDA OOM
        max_dim = 800
        h, w = cv_img.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            new_w = int(w * scale)
            new_h = int(h * scale)
            cv_img = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # OpenCV Preprocessing Pipeline for Dark/Shadowy Images
        # 1. Illumination correction (Shadow removal)
        # Dilate to erase dark ink, median blur to smooth out the paper background
        dilated = cv2.dilate(cv_img, np.ones((11, 11), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        
        # Divide original image by background to remove shadows/gradients
        bg_float = bg.astype(np.float32) + 1e-5
        img_float = cv_img.astype(np.float32)
        flat_illumination = np.clip(255.0 * (img_float / bg_float), 0, 255).astype(np.uint8)
        
        # 2. Gentle denoising to remove paper grain
        denoised = cv2.fastNlMeansDenoisingColored(flat_illumination, None, h=5, hColor=5, templateWindowSize=7, searchWindowSize=21)
        
        # 3. Gentle Unsharp Mask for blur reduction (much lighter than before)
        gaussian = cv2.GaussianBlur(denoised, (0, 0), 1.0)
        sharpened = cv2.addWeighted(denoised, 1.2, gaussian, -0.2, 0)
        
        # Convert to PIL RGB
        img_rgb = cv2.cvtColor(sharpened, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img_rgb)

        # Swin2SR has a pad_size requirement (64 px multiple for this model)
        # We pad, upscale, then crop to exact 4x output size.
        original_w, original_h = img.size
        pad_size = 64
        pad_w = (pad_size - original_w % pad_size) % pad_size
        pad_h = (pad_size - original_h % pad_size) % pad_size
        if pad_w > 0 or pad_h > 0:
            img_padded = Image.new("RGB", (original_w + pad_w, original_h + pad_h), (255, 255, 255))
            img_padded.paste(img, (0, 0))
        else:
            img_padded = img

        # Processor + inference
        inputs = self.processor(images=img_padded, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        # outputs.reconstruction shape: (1, 3, H*4, W*4)
        output_tensor = outputs.reconstruction.squeeze(0).clamp(0, 1)
        output_array = output_tensor.permute(1, 2, 0).cpu().numpy()
        enhanced_full = Image.fromarray((output_array * 255).astype(np.uint8))

        # Crop to exact 4x of original dimensions (remove padding)
        enhanced = enhanced_full.crop((0, 0, original_w * 4, original_h * 4))

        # Encode to PNG -> base64
        buf = io.BytesIO()
        enhanced.save(buf, format="PNG", optimize=False)
        enhanced_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return {"enhanced_b64": enhanced_b64}
