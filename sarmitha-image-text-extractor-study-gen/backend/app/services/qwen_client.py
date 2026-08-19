"""
Qwen Validation client — calls the Modal.com Qwen web endpoint.
Sends raw extracted text, receives validated/corrected text.
"""

import httpx
import asyncio

from app.core.config import settings

TIMEOUT = 300.0  # Large LLM inference can take some time if cold starting


async def validate_text(raw_text: str) -> str:
    """
    Send raw OCR text to the Modal Qwen endpoint for validation.
    Returns the corrected text string.

    Raises:
        ValueError: if Modal URL not configured.
        httpx.HTTPStatusError: on 4xx/5xx from Modal.
    """
    if not raw_text or not raw_text.strip():
        return ""

    url = settings.qwen_modal_url
    if not url:
        # If Qwen URL is not set, just gracefully fallback to raw text
        return raw_text

    payload = {"raw_text": raw_text}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    return response.json().get("validated_text", raw_text)
