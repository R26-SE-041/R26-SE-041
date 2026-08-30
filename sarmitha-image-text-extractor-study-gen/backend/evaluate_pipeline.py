"""Evaluate OCR pipeline variants on the held-out Google Drive test set.

Run with: modal run evaluate_pipeline.py
"""

import modal


BASE_MODEL = "hasindu-k/sinhala-handwritten-notes-v3"
FINE_MODEL = "sarmisarmitha/trocr-sinhala-handwritten-ocr"
FINE_SUBFOLDER = "02_final_model"
SWIN_MODEL = "sarmisarmitha/swin2sr-sinhala-image-enhancement"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.6.0",
        "torchvision==0.21.0",
        "transformers==4.57.6",
        "pillow==10.3.0",
        "numpy==1.26.4",
        "opencv-python-headless==4.10.0.84",
        "sentencepiece==0.2.0",
        "accelerate==1.2.1",
    )
    .add_local_dir("metrics_data/test", "/test_data", copy=True)
)

app = modal.App("sinhala-ocr-metrics-evaluation", image=image)


@app.function(gpu="A10G", timeout=3600)
def evaluate():
    import csv
    import gc
    import json
    import os
    import re
    import time
    import unicodedata

    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from transformers import (
        Swin2SRForImageSuperResolution,
        Swin2SRImageProcessor,
        TrOCRProcessor,
        VisionEncoderDecoderModel,
    )

    device = torch.device("cuda")

    def normalize(text):
        return " ".join(unicodedata.normalize("NFC", str(text or "")).split())

    def distance(source, target):
        previous = list(range(len(target) + 1))
        for i, left in enumerate(source, 1):
            current = [i]
            for j, right in enumerate(target, 1):
                current.append(min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left != right),
                ))
            previous = current
        return previous[-1]

    def scores(predictions, references, latency):
        char_errors = sum(distance(list(p), list(r)) for p, r in zip(predictions, references))
        char_total = sum(len(r) for r in references)
        word_errors = sum(distance(p.split(), r.split()) for p, r in zip(predictions, references))
        word_total = sum(len(r.split()) for r in references)
        exact = sum(p == r for p, r in zip(predictions, references)) / len(references)
        return {
            "cer": char_errors / char_total,
            "wer": word_errors / word_total,
            "exact_match": exact,
            "latency_seconds_per_image": latency,
            "samples": len(references),
        }

    def clean_app_text(text):
        text = unicodedata.normalize("NFC", str(text or ""))
        kept = "".join(
            char for char in text
            if "\u0d80" <= char <= "\u0dff"
            or char in {"\u200c", "\u200d"}
            or char.isspace()
            or unicodedata.category(char).startswith("P")
        )
        kept = re.sub(r"[ \t]+", " ", kept)
        kept = re.sub(r" *\n *", "\n", kept).strip()
        kept = re.sub(r"^[^\u0d80-\u0dff]+", "", kept)
        if sum("\u0d80" <= char <= "\u0dff" for char in kept) < 2:
            return ""
        return normalize(kept)

    image_index = {}
    for filename in os.listdir("/test_data/images"):
        path = os.path.join("/test_data/images", filename)
        image_index[os.path.splitext(filename)[0].lower()] = path

    samples = []
    with open("/test_data/data.csv", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            stem = os.path.splitext(str(row["file_name"]).strip())[0].lower()
            if stem in image_index:
                samples.append((image_index[stem], normalize(row["text"])))

    references = [reference for _, reference in samples]
    if len(samples) != 227:
        raise RuntimeError(f"Expected 227 matched samples, got {len(samples)}")

    def run_trocr(model_name, subfolder=None, input_images=None):
        kwargs = {"subfolder": subfolder} if subfolder else {}
        processor = TrOCRProcessor.from_pretrained(model_name, **kwargs)
        model = VisionEncoderDecoderModel.from_pretrained(model_name, **kwargs).to(device)
        model.eval()
        model.generation_config.max_length = 128
        model.generation_config.num_beams = 4
        model.generation_config.early_stopping = True
        model.generation_config.no_repeat_ngram_size = 0
        model.generation_config.do_sample = False

        paths_or_images = input_images if input_images is not None else [path for path, _ in samples]
        predictions = []
        elapsed = 0.0
        batch_size = 8

        # Warm-up is excluded from the latency measurement.
        warm_image = paths_or_images[0] if input_images is not None else Image.open(paths_or_images[0]).convert("RGB")
        if isinstance(warm_image, str):
            warm_image = Image.open(warm_image).convert("RGB")
        warm_values = processor(images=warm_image, return_tensors="pt").pixel_values.to(device)
        with torch.no_grad():
            model.generate(warm_values, max_length=128)

        for start in range(0, len(paths_or_images), batch_size):
            batch_items = paths_or_images[start:start + batch_size]
            batch_images = [
                Image.open(item).convert("RGB") if isinstance(item, str) else item.convert("RGB")
                for item in batch_items
            ]
            pixel_values = processor(images=batch_images, return_tensors="pt").pixel_values.to(device)
            torch.cuda.synchronize()
            began = time.perf_counter()
            with torch.no_grad():
                generated = model.generate(pixel_values, max_length=128)
            torch.cuda.synchronize()
            elapsed += time.perf_counter() - began
            decoded = processor.batch_decode(generated, skip_special_tokens=True)
            predictions.extend(normalize(text) for text in decoded)

        del model, processor
        gc.collect()
        torch.cuda.empty_cache()
        return predictions, elapsed / len(paths_or_images)

    base_predictions, base_latency = run_trocr(BASE_MODEL)
    fine_predictions, fine_latency = run_trocr(FINE_MODEL, FINE_SUBFOLDER)

    swin_processor = Swin2SRImageProcessor.from_pretrained(SWIN_MODEL)
    swin_model = Swin2SRForImageSuperResolution.from_pretrained(SWIN_MODEL).to(device)
    swin_model.eval()
    enhanced_images = []
    enhancement_elapsed = 0.0

    for path, _ in samples:
        cv_img = cv2.imread(path, cv2.IMREAD_COLOR)
        height, width = cv_img.shape[:2]
        if max(height, width) > 800:
            scale = 800 / float(max(height, width))
            cv_img = cv2.resize(
                cv_img,
                (int(width * scale), int(height * scale)),
                interpolation=cv2.INTER_AREA,
            )
        dilated = cv2.dilate(cv_img, np.ones((11, 11), np.uint8))
        background = cv2.medianBlur(dilated, 21)
        flattened = np.clip(
            255.0 * (cv_img.astype(np.float32) / (background.astype(np.float32) + 1e-5)),
            0,
            255,
        ).astype(np.uint8)
        denoised = cv2.fastNlMeansDenoisingColored(
            flattened, None, h=5, hColor=5, templateWindowSize=7, searchWindowSize=21
        )
        gaussian = cv2.GaussianBlur(denoised, (0, 0), 1.0)
        sharpened = cv2.addWeighted(denoised, 1.2, gaussian, -0.2, 0)
        original = Image.fromarray(cv2.cvtColor(sharpened, cv2.COLOR_BGR2RGB))
        original_width, original_height = original.size
        pad_width = (64 - original_width % 64) % 64
        pad_height = (64 - original_height % 64) % 64
        padded = Image.new(
            "RGB",
            (original_width + pad_width, original_height + pad_height),
            (255, 255, 255),
        )
        padded.paste(original, (0, 0))
        inputs = swin_processor(images=padded, return_tensors="pt").to(device)
        torch.cuda.synchronize()
        began = time.perf_counter()
        with torch.no_grad():
            reconstruction = swin_model(**inputs).reconstruction
        torch.cuda.synchronize()
        enhancement_elapsed += time.perf_counter() - began
        output = reconstruction.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().numpy()
        enhanced = Image.fromarray((output * 255).astype(np.uint8)).crop(
            (0, 0, original_width * 4, original_height * 4)
        )
        enhanced_images.append(enhanced)

    del swin_model, swin_processor
    gc.collect()
    torch.cuda.empty_cache()

    enhanced_predictions, enhanced_ocr_latency = run_trocr(
        FINE_MODEL, FINE_SUBFOLDER, enhanced_images
    )
    enhanced_latency = enhancement_elapsed / len(samples) + enhanced_ocr_latency
    final_predictions = [clean_app_text(text) for text in fine_predictions]

    result = {
        "base_trocr": scores(base_predictions, references, base_latency),
        "fine_tuned_trocr": scores(fine_predictions, references, fine_latency),
        "swinsr_plus_trocr": scores(enhanced_predictions, references, enhanced_latency),
        "final_application_core": scores(
            final_predictions,
            references,
            enhancement_elapsed / len(samples) + fine_latency,
        ),
        "latency_note": "Warm GPU compute per image; excludes Modal/network/translation overhead.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


@app.local_entrypoint()
def main():
    result = evaluate.remote()
    print(result)
