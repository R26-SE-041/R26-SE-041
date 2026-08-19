"""
TrOCR client — calls the Modal.com TrOCR web endpoint.
Sends base64-encoded image, receives extracted text.
"""

import base64
import httpx

from app.core.config import settings

TIMEOUT = 300.0  # TrOCR large model inference


async def extract_text(image_bytes: bytes) -> str:
    """
    Send raw image bytes to the Modal TrOCR endpoint.
    Returns the extracted text string.

    Raises:
        ValueError: if Modal URL not configured.
        httpx.HTTPStatusError: on 4xx/5xx from Modal.
    """
    url = settings.trocr_modal_url
    if not url:
        raise ValueError(
            "TROCR_MODAL_URL is not set. "
            "Deploy modal_functions/trocr_app.py and add the URL to .env"
        )

    payload = {"image_b64": base64.b64encode(image_bytes).decode("utf-8")}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    return response.json().get("text", "")

async def extract_lines(image_bytes: bytes) -> list:
    url = settings.trocr_lines_modal_url
    if not url:
        raise ValueError("TROCR_LINES_MODAL_URL is not set.")

    payload = {"image_b64": base64.b64encode(image_bytes).decode("utf-8")}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    return response.json().get("lines", [])
