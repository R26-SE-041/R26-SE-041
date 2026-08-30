"""
Translate client — calls the Modal.com TranslateGemma web endpoint.
"""

import httpx

from app.core.config import settings
from app.core.http import modal_client

TIMEOUT = 60.0  # Allow up to 60s for translation


async def translate_text(text: str, target_language: str) -> str:
    """
    Send Sinhala text to the Modal TranslateGemma endpoint.
    target_language: "ta" for Tamil, "en" for English.
    Returns translated text.

    Raises:
        ValueError: if Modal URL not configured.
        httpx.HTTPStatusError: on 4xx/5xx from Modal.
    """
    url = settings.translate_modal_url
    if not url:
        return "" # Silently return empty if translation is not configured

    payload = {
        "text": text,
        "target_language": target_language
    }

    async with modal_client(TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    translated_text: str = response.json()["translated_text"]
    return translated_text
