"""
Visual OCR Validation client — calls the Modal.com Qwen2-VL web endpoint.
Sends base64 cropped image + raw extracted text, receives verified text.
"""

import httpx
from app.core.config import settings

TIMEOUT = 300.0

async def verify_text(image_b64: str, raw_text: str) -> str:
    if not image_b64 or not raw_text.strip():
        return raw_text

    url = settings.visual_ocr_modal_url
    if not url:
        return raw_text

    payload = {
        "image_b64": image_b64,
        "raw_text": raw_text
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    return response.json().get("verified_text", raw_text)
