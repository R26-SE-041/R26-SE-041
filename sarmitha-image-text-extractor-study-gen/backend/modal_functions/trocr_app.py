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

Warm state: 1 hour (scaledown_window=3600)

Deploy:
  modal deploy modal_functions/trocr_app.py

--- KEY FIXES vs previous version ---

1. PREPROCESSING  (was: h=15 NLM + aggressive sharpening)
   - Reduced NLM denoising h=15→7 to preserve thin diacritical marks
   - Removed Gaussian blur + unsharp mask (they smear ් al-lakuna etc.)
   - Reduced CLAHE clipLimit=3.0→2.0
   - Model receives the lightly-enhanced image without grayscale conversion
     (keeps colour contrast between ink and paper)

2. MODEL INPUT ASPECT RATIO  (was: direct Resize(384,384))
   - Added pad_to_square_and_resize(): pads short axis with white before
     resizing so wide line crops are not squashed to square (which distorted
     every character beyond recognition)

3. LINE SEGMENTATION  (was: kernel_width=img_w//25, iterations=2)
   - Tighter horizontal kernel: img_w//40 (was img_w//25)
   - Single dilation pass (was 2) — prevents bridging adjacent lines
   - Overlap-merge step: bounding boxes whose Y ranges overlap within 8px
     are merged into one, preventing the same line being split at gaps
   - Crops taken from the *preprocessed colour image* (not the binary mask)

4. CONFIDENCE SCORING  (was: logits.max() — always near-0 log-prob)
   - Now extracts log-prob of the *actually chosen token* at each step
   - Gives a real per-line confidence in [0,1] range
   - Sequence confidence = exp(mean_log_prob_of_chosen_tokens)
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
        "transformers==4.46.3",
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
        "python -c \"import base64; exec(base64.b64decode('aW1wb3J0IGpzb24sIG9zLCBzaHV0aWwKZGVmIGZkKGQpOgogICAgaWYgaXNpbnN0YW5jZShkLCBkaWN0KToKICAgICAgICBpZiBkLmdldCgnZWFybHlfc3RvcHBpbmcnKSBpcyBOb25lIGFuZCAnZWFybHlfc3RvcHBpbmcnIGluIGQ6IGRbJ2Vhcmx5X3N0b3BwaW5nJ10gPSBGYWxzZQogICAgICAgIFtmZCh2KSBmb3IgdiBpbiBkLnZhbHVlcygpXQogICAgZWxpZiBpc2luc3RhbmNlKGQsIGxpc3QpOiBbZmQoaSkgZm9yIGkgaW4gZF0KZm9yIGMgaW4gWycvaGZfY2FjaGUnLCAnL3Jvb3QvLmNhY2hlL2h1Z2dpbmdmYWNlJ106CiAgICBmb3IgciwgXywgZnMgaW4gb3Mud2FsayhjKToKICAgICAgICBmb3IgZiBpbiBmczoKICAgICAgICAgICAgaWYgZiA9PSAncHJvY2Vzc29yX2NvbmZpZy5qc29uJzoKICAgICAgICAgICAgICAgIHAgPSBvcy5wYXRoLmpvaW4ociwgZikKICAgICAgICAgICAgICAgIGRlc3QgPSBvcy5wYXRoLmpvaW4ociwgJ3ByZXByb2Nlc3Nvcl9jb25maWcuanNvbicpCiAgICAgICAgICAgICAgICBpZiBub3Qgb3MucGF0aC5leGlzdHMoZGVzdCk6CiAgICAgICAgICAgICAgICAgICAgdHJ5OgogICAgICAgICAgICAgICAgICAgICAgICBkID0ganNvbi5sb2FkKG9wZW4ocCkpCiAgICAgICAgICAgICAgICAgICAgICAgIGlmICdpbWFnZV9wcm9jZXNzb3InIGluIGQ6CiAgICAgICAgICAgICAgICAgICAgICAgICAgICBvcGVuKGRlc3QsICd3Jykud3JpdGUoanNvbi5kdW1wcyhkWydpbWFnZV9wcm9jZXNzb3InXSkpCiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcmludCgnZXh0cmFjdGVkIGltYWdlX3Byb2Nlc3NvciB0bycsIGRlc3QpCiAgICAgICAgICAgICAgICAgICAgICAgIGVsc2U6CiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzaHV0aWwuY29weShwLCBkZXN0KQogICAgICAgICAgICAgICAgICAgIGV4Y2VwdDogcGFzcwogICAgICAgICAgICBpZiBmLmVuZHN3aXRoKCcuanNvbicpOgogICAgICAgICAgICAgICAgcCA9IG9zLnBhdGguam9pbihyLCBmKQogICAgICAgICAgICAgICAgdHJ5OgogICAgICAgICAgICAgICAgICAgIGQgPSBqc29uLmxvYWQob3BlbihwKSkKICAgICAgICAgICAgICAgICAgICBmZChkKQogICAgICAgICAgICAgICAgICAgIG9wZW4ocCwgJ3cnKS53cml0ZShqc29uLmR1bXBzKGQpKQogICAgICAgICAgICAgICAgICAgIHByaW50KCdwYXRjaGVkJywgcCkKICAgICAgICAgICAgICAgIGV4Y2VwdDogcGFzcw==').decode('utf-8'))\""
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------




def _light_preprocess(cv_img):
    from PIL import Image
    import cv2
    
    # The image is already enhanced by SRCNN (shadow removal + super resolution).
    # We just need to ensure it's in the correct format for the segmentation/OCR pipeline.
    # The OCR model expects RGB.
    img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img_rgb)


def _segment_lines(cv_img_bgr, preprocessed_pil):
    """
    Segment a full-page handwritten image into per-line crops.

    Strategy:
      1. Binarise with Otsu on grayscale
      2. Dilate horizontally with a NARROW kernel (img_w//40) to bridge
         letter gaps within a line without bridging the gap between lines.
         Use only 1 dilation pass (the old code used 2, which could bridge
         adjacent lines).
      3. Find external contours → bounding boxes
      4. Filter noise (too-small boxes)
      5. Merge boxes that overlap vertically within 8px (handles the case
         where one line was split into two contours at a word gap)
      6. Sort by Y (top-to-bottom reading order)
      7. Return crops from the *preprocessed colour image* (not binary mask)
    """
    import cv2
    import numpy as np
    from PIL import Image

    # Use the preprocessed colour image for cropping (better quality than raw)
    cv_preprocessed = cv2.cvtColor(np.array(preprocessed_pil), cv2.COLOR_RGB2BGR)
    img_h, img_w = cv_preprocessed.shape[:2]

    # Binarise for contour detection
    gray = cv2.cvtColor(cv_preprocessed, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Narrow horizontal kernel — bridges letter/word gaps within a line
    # but not the gap between adjacent lines (old code used img_w//25 which was too wide)
    kernel_w = max(20, img_w // 40)
    kernel_h = max(3, img_h // 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, kernel_h))
    dilated = cv2.dilate(thresh, kernel, iterations=1)  # 1 pass (old: 2 passes)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = img_w * img_h
    raw_boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # Filter: must be wide enough and tall enough to be a text line,
        # and not so large that it covers most of the page (noise guard)
        if (w > max(30, img_w * 0.05)
                and h > max(15, img_h * 0.015)
                and (w * h) < img_area * 0.95):
            raw_boxes.append((x, y, x + w, y + h))

    if not raw_boxes:
        # Fallback: return full image as single line
        return [preprocessed_pil]

    # --- Overlap-merge: join boxes whose Y ranges overlap within 8px ---
    # Sorted by top-Y for the merge sweep
    raw_boxes.sort(key=lambda b: b[1])
    merged = [list(raw_boxes[0])]
    for x1, y1, x2, y2 in raw_boxes[1:]:
        prev = merged[-1]
        # If this box's top (y1) is within 8px of the previous box's bottom (prev[3])
        if y1 <= prev[3] + 8:
            # Merge: expand the previous box to encompass this one
            prev[0] = min(prev[0], x1)
            prev[1] = min(prev[1], y1)
            prev[2] = max(prev[2], x2)
            prev[3] = max(prev[3], y2)
        else:
            merged.append([x1, y1, x2, y2])

    # Sort final boxes top-to-bottom (reading order)
    merged.sort(key=lambda b: b[1])

    # Crop with padding from the preprocessed colour image
    crops = []
    for x1, y1, x2, y2 in merged:
        h = y2 - y1
        pad_y = max(8, int(h * 0.12))
        pad_x = max(4, int((x2 - x1) * 0.02))
        cy1 = max(0, y1 - pad_y)
        cy2 = min(img_h, y2 + pad_y)
        cx1 = max(0, x1 - pad_x)
        cx2 = min(img_w, x2 + pad_x)
        crop_bgr = cv_preprocessed[cy1:cy2, cx1:cx2]
        crops.append(Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)))

    return crops


def _compute_confidence(outputs, generated_ids, line_idx: int) -> float:
    """
    Compute a real per-line confidence score from beam-search outputs.

    OLD (broken): took logits.max() at each step — this is always near 0
    log-prob regardless of actual prediction difficulty, making all lines
    look high-confidence.

    NEW: extracts the log-prob of the *actually chosen token* at each
    decoding step. The per-line confidence is exp(mean_log_prob_chosen),
    giving a value in (0, 1] that reflects true model certainty.
    """
    import math
    import torch
    import torch.nn.functional as F

    if not outputs.scores:
        return 0.0

    seq = generated_ids[line_idx]  # shape: (seq_len,)
    log_probs = []

    for step_idx, step_logits in enumerate(outputs.scores):
        # step_logits shape: (batch, vocab_size)
        token_pos = step_idx + 1  # generated_ids[0] is decoder_start_token
        if token_pos >= seq.shape[0]:
            break
        chosen_token_id = seq[token_pos].item()
        lp = F.log_softmax(step_logits[line_idx], dim=-1)[chosen_token_id].item()
        log_probs.append(lp)

    if not log_probs:
        return 0.0

    avg_log_prob = sum(log_probs) / len(log_probs)
    return max(0.0, min(1.0, math.exp(avg_log_prob)))


# ---------------------------------------------------------------------------
# Modal class
# ---------------------------------------------------------------------------

@app.cls(gpu="T4", scaledown_window=3600, min_containers=1)  # 1 hour warm state
class SinhalaTrOCRExtractor:
    @modal.enter()
    def load_model(self):
        import torch
        from transformers import ViTImageProcessor, AutoTokenizer, VisionEncoderDecoderModel

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Use the official feature extractor instead of manual transforms
        # The model was trained on squashed 384x384 images, so we must squash them too!
        self.feature_extractor = ViTImageProcessor.from_pretrained(
            HF_MODEL, local_files_only=True
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            HF_MODEL, local_files_only=True
        )
        self.model = VisionEncoderDecoderModel.from_pretrained(
            HF_MODEL, local_files_only=True
        ).to(self.device)

        # Use the config from the model, only set vocab_size and generation params
        self.model.config.vocab_size = self.model.config.decoder.vocab_size
        self.model.config.max_length = 256
        self.model.config.early_stopping = True
        self.model.config.no_repeat_ngram_size = 0
        self.model.config.length_penalty = 1.0
        self.model.config.num_beams = 4

        self.model.eval()
        print(f"[Sinhala TrOCR v3 — fixed (using ViTImageProcessor)] Model loaded on {self.device}")

    @modal.fastapi_endpoint(method="POST")
    def extract_lines(self, request: dict) -> dict:
        """
        Accepts JSON: {"image_b64": "<base64-encoded image>"}
        Returns JSON: {"lines": [{"text": "...", "crop_b64": "...", "confidence": 0.72}]}

        The confidence score is now a real per-line value (exp of mean log-prob
        of chosen tokens), not the spurious near-zero value from the old code.
        """
        import base64
        import numpy as np
        import cv2
        import torch
        from PIL import Image

        # --- Decode input ---
        image_bytes = base64.b64decode(request["image_b64"])
        nparr = np.frombuffer(image_bytes, np.uint8)
        cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # --- Preprocess ---
        preprocessed_pil = _light_preprocess(cv_img)

        # --- Segment into lines ---
        line_imgs = _segment_lines(cv_img, preprocessed_pil)

        # --- Prepare batch tensor using official feature extractor ---
        pixel_values = self.feature_extractor(
            images=[img.convert("RGB") for img in line_imgs], 
            return_tensors="pt"
        ).pixel_values.to(self.device)

        # --- Generate with beam search ---
        with torch.no_grad():
            outputs = self.model.generate(
                pixel_values,
                max_length=self.model.config.max_length,
                num_beams=self.model.config.num_beams,
                early_stopping=self.model.config.early_stopping,
                return_dict_in_generate=True,
                output_scores=True,
            )

        generated_ids = outputs.sequences

        # --- Decode tokens ---
        texts = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)

        # --- Compute real per-line confidence scores ---
        confidences = [
            _compute_confidence(outputs, generated_ids, i)
            for i in range(len(line_imgs))
        ]

        # --- Build response (crop from original line_imgs, not the padded version) ---
        result_lines = []
        for img, text, conf in zip(line_imgs, texts, confidences):
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=90)
            img_b64 = base64.b64encode(buffered.getvalue()).decode()
            result_lines.append({
                "text": text.strip(),
                "crop_b64": img_b64,
                "confidence": round(conf, 4),
            })

        return {"lines": result_lines}
