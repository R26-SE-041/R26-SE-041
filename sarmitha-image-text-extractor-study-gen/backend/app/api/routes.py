"""
API routes for the image enhancement + OCR pipeline.

Pipeline (POST /api/process):
  1. SRCNN enhancement (Modal)     — 4× super-resolution
  2. TrOCR line extraction (Modal) — per-line crop + text + confidence
  3. SinhaLM context improvement   — full-page contextual correction (optional,
                                     skipped if SINHALM_MODAL_URL not set)

Other endpoints:
  POST /api/enhance  — enhancement only
  POST /api/ocr      — OCR only (pass an already-good image)
"""

import base64

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services import srcnn_client, trocr_client, sinhalm_client, visual_client

router = APIRouter(prefix="/api")

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


def _validate_upload(file: UploadFile, data: bytes) -> None:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Accepted: {', '.join(ALLOWED_CONTENT_TYPES)}",
        )
    if len(data) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {mb} MB.",
        )


# ---------------------------------------------------------------------------
# POST /api/process  — full pipeline
# ---------------------------------------------------------------------------
@router.post("/process")
async def process_image(file: UploadFile = File(...)):
    """
    Full pipeline:
      1. Enhance with SRCNN (Modal)
      2. Extract lines with TrOCR (Modal) -> gets crops & text per line
      3. For each line:
         a. If low confidence: Visual OCR Agent (Qwen2-VL) -> SinhaLM
         b. If high confidence: SinhaLM Validation Agent
         
    Returns:
      {
        "original_b64":  "<base64 PNG of original>",
        "enhanced_b64":  "<base64 PNG of SRCNN output>",
        "extracted_text": "...",
        "lines": [
            {
               "crop_b64": "...",
               "raw_text": "...",
               "visual_text": "...", # optional
               "final_text": "...",
               "confidence": 0.99
            }
        ]
      }
    """
    raw_bytes = await file.read()
    _validate_upload(file, raw_bytes)

    # Step 1 — SRCNN enhancement
    try:
        enhanced_bytes = await srcnn_client.enhance_image(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SRCNN service error: {exc.__class__.__name__} - {exc}")

    # Step 2 — TrOCR OCR (line-by-line)
    try:
        lines_data = await trocr_client.extract_lines(enhanced_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TrOCR service error: {exc.__class__.__name__} - {exc}")

    # Step 3 — Normalise line data from TrOCR into the response shape
    processed_lines = [
        {
            "crop_b64":   line["crop_b64"],
            "raw_text":   line["text"],
            "visual_text": line["text"],   # kept for frontend compatibility
            "final_text":  line["text"],   # will be overwritten in Step 4
            "confidence":  line["confidence"],
        }
        for line in lines_data
    ]

    raw_full_text = "\n".join(line["raw_text"] for line in processed_lines)

    # Step 4 — SinhaLM full-page context improvement (optional)
    # If SINHALM_MODAL_URL is not set, sinhalm_client.validate_text returns
    # raw_text unchanged, so this step is safely skipped.
    context_improved = False
    try:
        improved_text = await sinhalm_client.validate_text(raw_full_text)
        if improved_text and improved_text.strip() and improved_text != raw_full_text:
            context_improved = True
            # Distribute the improved lines back to the per-line results
            improved_lines = improved_text.split("\n")
            for i, pline in enumerate(processed_lines):
                pline["final_text"] = improved_lines[i] if i < len(improved_lines) else pline["raw_text"]
            final_full_text = improved_text
        else:
            final_full_text = raw_full_text
    except Exception as exc:
        # Log but never crash — OCR result is still valuable even without LLM pass
        import logging
        logging.getLogger(__name__).warning("SinhaLM context improvement failed: %s", exc)
        final_full_text = raw_full_text

    return JSONResponse(
        {
            "original_b64":    base64.b64encode(raw_bytes).decode(),
            "enhanced_b64":    base64.b64encode(enhanced_bytes).decode(),
            "extracted_text":  final_full_text,
            "lines":           processed_lines,
            "context_improved": context_improved,
        }
    )


# ---------------------------------------------------------------------------
# POST /api/enhance  — enhancement only
# ---------------------------------------------------------------------------
@router.post("/enhance")
async def enhance_only(file: UploadFile = File(...)):
    """Enhance image resolution with SRCNN only."""
    raw_bytes = await file.read()
    _validate_upload(file, raw_bytes)

    try:
        enhanced_bytes = await srcnn_client.enhance_image(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SRCNN service error: {exc}")

    return JSONResponse(
        {
            "original_b64": base64.b64encode(raw_bytes).decode(),
            "enhanced_b64": base64.b64encode(enhanced_bytes).decode(),
        }
    )


# ---------------------------------------------------------------------------
# POST /api/ocr  — OCR only
# ---------------------------------------------------------------------------
@router.post("/ocr")
async def ocr_only(file: UploadFile = File(...)):
    """Extract text from an image using TrOCR only."""
    raw_bytes = await file.read()
    _validate_upload(file, raw_bytes)

    try:
        text = await trocr_client.extract_text(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TrOCR service error: {exc}")

    return JSONResponse({"extracted_text": text})


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------
@router.get("/health")
async def health():
    return {
        "status": "ok",
        "srcnn_configured": bool(settings.srcnn_modal_url),
        "trocr_configured": bool(settings.trocr_modal_url),
    }
