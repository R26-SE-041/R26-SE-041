"""Sinhala paragraph OCR service using the final OneClick inference pipeline.

Primary model files are read from a persistent Modal Volume. The secondary
model used by the notebook is cached in the container image. Both models are
loaded once per container and are used for inference only.

Upload the complete primary model folder before deployment:
  modal volume create sinhala-trocr-models
  modal volume put sinhala-trocr-models ./sinhala_trocr_extra_data_v1 /sinhala_trocr_extra_data_v1

Deploy without changing the live service until ready:
  modal deploy modal_functions/trocr_app.py
"""

import io
import json
import threading
from pathlib import Path

import modal


PRIMARY_VOLUME_NAME = "sinhala-trocr-models"
PRIMARY_VOLUME_ROOT = "/models"
PRIMARY_MODEL_DIR = f"{PRIMARY_VOLUME_ROOT}/sinhala_trocr_extra_data_v1"
SECONDARY_MODEL_ID = "eshangj/TrOCR-Sinhala-finetuned"
HF_CACHE = "/hf_cache"

primary_volume = modal.Volume.from_name(PRIMARY_VOLUME_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.6.0",
        "torchvision==0.21.0",
        "transformers==5.18.0",
        "pillow==10.3.0",
        "sentencepiece==0.2.0",
        "accelerate==0.30.1",
        "opencv-python-headless==4.10.0.84",
        "fastapi[standard]",
    )
    .env({"HF_HOME": HF_CACHE})
    .run_commands(
        "python -c \"from huggingface_hub import snapshot_download; "
        f"snapshot_download(repo_id='{SECONDARY_MODEL_ID}'); "
        "print('Secondary TrOCR model cached')\""
    )
)

app = modal.App("sinhala-trocr-ocr-service", image=image)


def component_groups(image, tolerance):
    """Detect connected handwriting bodies exactly as in OneClick."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    background = cv2.GaussianBlur(gray, (0, 0), max(5, min(height, width) * 0.05))
    flattened = cv2.divide(gray, background, scale=255)
    _, mask = cv2.threshold(
        flattened, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    candidates = []
    for index in range(1, count):
        x, y, component_width, component_height, area = map(int, stats[index])
        if (
            area >= 15
            and component_height >= 5
            and component_width / max(1, component_height) < 15
            and component_height < height * 0.5
            and x > 0
            and y > 0
            and x + component_width < width
            and y + component_height < height
        ):
            candidates.append(index)
    if not candidates:
        raise ValueError("No text bodies detected. Crop the paragraph area.")

    heights = np.array([stats[index, 3] for index in candidates])
    weights = np.array([stats[index, 4] for index in candidates])
    order = np.argsort(heights)
    median_index = np.searchsorted(np.cumsum(weights[order]), weights.sum() / 2)
    typical = float(heights[order[median_index]])
    bodies = [index for index in candidates if stats[index, 3] >= 0.65 * typical]
    groups = []
    for index in sorted(bodies, key=lambda key: stats[key, 1] + stats[key, 3] / 2):
        center = float(stats[index, 1] + stats[index, 3] / 2)
        if groups and abs(
            center
            - np.median([stats[item, 1] + stats[item, 3] / 2 for item in groups[-1]])
        ) <= float(tolerance) * typical:
            groups[-1].append(index)
        else:
            groups.append([index])

    groups = [
        group
        for group in groups
        if len(group) >= 3
        or (
            max(stats[index, 0] + stats[index, 2] for index in group)
            - min(stats[index, 0] for index in group)
            >= 3 * typical
            and sum(stats[index, 4] for index in group) >= typical * typical * 0.8
        )
    ]
    return mask, labels, stats, groups, typical


def straighten_text(image, tolerance):
    """Apply the notebook's conservative page deskewing."""
    import cv2
    import numpy as np
    from PIL import Image

    _, _, stats, groups, typical = component_groups(image, tolerance)
    slopes = []
    for group in groups:
        centers = [
            (stats[index, 0] + stats[index, 2] / 2, stats[index, 1] + stats[index, 3] / 2)
            for index in group
        ]
        span = max(x for x, _ in centers) - min(x for x, _ in centers)
        for position, (x, y) in enumerate(centers):
            for next_x, next_y in centers[position + 1 :]:
                if abs(next_x - x) > max(3 * typical, span * 0.4):
                    slopes.append((next_y - y) / (next_x - x))
    angle = float(np.degrees(np.arctan(np.median(slopes)))) if slopes else 0.0
    if not 0.5 <= abs(angle) <= 8:
        return image

    width, height = image.size
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1)
    cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_width = int(np.ceil(height * sine + width * cosine))
    new_height = int(np.ceil(height * cosine + width * sine))
    matrix[0, 2] += new_width / 2 - width / 2
    matrix[1, 2] += new_height / 2 - height / 2
    fill = tuple(int(value) for value in np.median(np.asarray(image).reshape(-1, 3), axis=0))
    rotated = cv2.warpAffine(
        np.asarray(image),
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=fill,
    )
    return Image.fromarray(rotated)


def detect_lines(image, gap=0.65, padding=8):
    """Return OneClick line crops and top-to-bottom bounding boxes."""
    import numpy as np

    if min(image.size) < 16:
        raise ValueError("Image too small.")
    image = straighten_text(image, gap)
    mask, _, stats, groups, _ = component_groups(image, gap)
    width, height = image.size
    ranges = [
        (
            int(min(stats[index, 1] for index in group)),
            int(max(stats[index, 1] + stats[index, 3] for index in group)),
        )
        for group in groups
    ]
    ranges.sort()
    if not ranges:
        raise ValueError("No complete text lines detected. Crop to the text area.")

    crops, boxes = [], []
    for index, (top, bottom) in enumerate(ranges):
        low = 0 if index == 0 else (ranges[index - 1][1] + top) // 2
        high = height if index == len(ranges) - 1 else (bottom + ranges[index + 1][0]) // 2
        y0 = max(low, top - int(padding))
        y1 = min(high, bottom + int(padding))
        columns = np.flatnonzero(np.any(mask[top:bottom] > 0, axis=0))
        x0 = max(0, int(columns[0]) - int(padding)) if len(columns) else 0
        x1 = min(width, int(columns[-1]) + int(padding) + 1) if len(columns) else width
        if x1 <= x0 or y1 <= y0:
            continue
        crops.append(image.crop((x0, y0, x1, y1)))
        boxes.append((x0, y0, x1, y1))
    return crops, boxes


def _validate_primary_model():
    model_dir = Path(PRIMARY_MODEL_DIR)
    required = ["config.json"]
    missing = [name for name in required if not (model_dir / name).is_file()]
    weight_files = [
        model_dir / "model.safetensors",
        model_dir / "model.safetensors.index.json",
        model_dir / "pytorch_model.bin",
    ]
    if not any(path.is_file() for path in weight_files):
        missing.append("model.safetensors (or equivalent model weights)")
    if missing:
        raise FileNotFoundError(
            f"Primary model folder {PRIMARY_MODEL_DIR} is incomplete; missing: "
            + ", ".join(missing)
        )


def _load_ocr(source, local_only):
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    processor = TrOCRProcessor.from_pretrained(source, local_files_only=local_only)
    model, info = VisionEncoderDecoderModel.from_pretrained(
        source, local_files_only=local_only, output_loading_info=True
    )
    issues = {
        key: info.get(key, [])
        for key in ["missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs"]
    }
    print(f"[OneClick OCR] Loading diagnostics for {source}:")
    print(json.dumps(issues, ensure_ascii=False, indent=2, default=str))
    if any(issues.values()):
        raise RuntimeError(f"Model loading reported weight/key issues for {source}")
    return processor, model


@app.cls(
    gpu="T4",
    scaledown_window=300,
    timeout=600,
    volumes={PRIMARY_VOLUME_ROOT: primary_volume},
)
class SinhalaTrOCRExtractor:
    @modal.enter()
    def load_models(self):
        import torch

        _validate_primary_model()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_lock = threading.RLock()

        self.primary_processor, self.primary_model = _load_ocr(PRIMARY_MODEL_DIR, True)
        self.secondary_processor, self.secondary_model = _load_ocr(
            SECONDARY_MODEL_ID, True
        )
        self.primary_model.to(self.device).eval()
        self.secondary_model.to(self.device).eval()

        print(f"[OneClick OCR] Primary model: {PRIMARY_MODEL_DIR}")
        print(f"[OneClick OCR] Secondary model: {SECONDARY_MODEL_ID}")
        print("[OneClick OCR] Pipeline: deskew -> line detection -> dual recognition -> primary CLL selection -> paragraph")
        print(f"[OneClick OCR] Device: {self.device}; request concurrency: 1")

    def _ocr_batch(self, crops, processor, model):
        import torch

        texts = []
        batch_size = 4 if self.device == "cuda" else 1
        for start in range(0, len(crops), batch_size):
            inputs = processor(images=crops[start : start + batch_size], return_tensors="pt")
            with torch.inference_mode():
                generated = model.generate(
                    inputs.pixel_values.to(self.device),
                    max_length=128,
                    num_beams=4,
                    do_sample=False,
                )
            texts.extend(
                text.strip()
                for text in processor.batch_decode(generated, skip_special_tokens=True)
            )
        return texts

    def _score_candidates(self, crops, texts):
        import torch
        import torch.nn.functional as functional

        values = []
        batch_size = 4 if self.device == "cuda" else 1
        for start in range(0, len(texts), batch_size):
            batch_text = texts[start : start + batch_size]
            batch_crops = crops[start : start + len(batch_text)]
            pixels = self.primary_processor(
                images=batch_crops, return_tensors="pt"
            ).pixel_values.to(self.device)
            tokens = self.primary_processor.tokenizer(
                batch_text,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            labels = tokens.input_ids.to(self.device)
            valid = tokens.attention_mask.to(self.device).bool()
            labels = labels.masked_fill(~valid, -100)
            with torch.inference_mode():
                logits = self.primary_model(pixel_values=pixels, labels=labels).logits
                losses = functional.cross_entropy(
                    logits.transpose(1, 2), labels, reduction="none", ignore_index=-100
                )
                scores = -(losses.sum(dim=1) / valid.sum(dim=1).clamp_min(1))
            values.extend(scores.float().cpu().tolist())
        return values

    def _extract(self, request):
        import base64

        from PIL import Image, ImageOps

        encoded = request.get("image_b64")
        if not encoded:
            raise ValueError("image_b64 is required")
        image = ImageOps.exif_transpose(
            Image.open(io.BytesIO(base64.b64decode(encoded)))
        ).convert("RGB")
        crops, boxes = detect_lines(image)

        with self.model_lock:
            primary_texts = self._ocr_batch(
                crops, self.primary_processor, self.primary_model
            )
            secondary_texts = self._ocr_batch(
                crops, self.secondary_processor, self.secondary_model
            )
            final_texts = list(primary_texts)
            candidate_crops, candidate_texts, differing_lines = [], [], []
            for index, (primary, secondary) in enumerate(
                zip(primary_texts, secondary_texts)
            ):
                if not primary and secondary:
                    final_texts[index] = secondary
                elif primary and secondary and primary != secondary:
                    differing_lines.append(index)
                    candidate_crops.extend([crops[index], crops[index]])
                    candidate_texts.extend([primary, secondary])
            if differing_lines:
                scores = self._score_candidates(candidate_crops, candidate_texts)
                for score_index, line_index in enumerate(differing_lines):
                    if scores[2 * score_index + 1] > scores[2 * score_index]:
                        final_texts[line_index] = secondary_texts[line_index]

        final_texts = [text if text.strip() else "[unclear]" for text in final_texts]
        lines = []
        for crop, box, text in zip(crops, boxes, final_texts):
            buffer = io.BytesIO()
            crop.save(buffer, format="JPEG", quality=90)
            lines.append(
                {
                    "text": text,
                    "crop_b64": base64.b64encode(buffer.getvalue()).decode("utf-8"),
                    "confidence": None,
                    "box": list(box),
                }
            )
        paragraph = " ".join(final_texts)
        return {"text": paragraph, "paragraph": paragraph, "lines": lines}

    @modal.fastapi_endpoint(method="POST")
    def extract_lines(self, request: dict) -> dict:
        return self._extract(request)

    @modal.fastapi_endpoint(method="POST")
    def extract_text(self, request: dict) -> dict:
        return self._extract(request)
