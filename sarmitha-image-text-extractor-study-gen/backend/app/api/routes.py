"""
API routes for the image enhancement + OCR pipeline.

Endpoints:
  POST /api/process  — full pipeline (enhance + OCR), returns both results
  POST /api/enhance  — enhancement only
  POST /api/ocr      — OCR only (pass an already-good image)
"""

import base64

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services import srcnn_client, trocr_client

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
      2. Extract text with TrOCR (Modal)

    Returns:
      {
        "original_b64":  "<base64 PNG of original>",
        "enhanced_b64":  "<base64 PNG of SRCNN output>",
        "extracted_text": "..."
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
        raise HTTPException(status_code=502, detail=f"SRCNN service error: {exc}")

    # Step 2 — TrOCR OCR on the enhanced image
    try:
        text = await trocr_client.extract_text(enhanced_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TrOCR service error: {exc}")

    return JSONResponse(
        {
            "original_b64": base64.b64encode(raw_bytes).decode(),
            "enhanced_b64": base64.b64encode(enhanced_bytes).decode(),
            "extracted_text": text,
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
