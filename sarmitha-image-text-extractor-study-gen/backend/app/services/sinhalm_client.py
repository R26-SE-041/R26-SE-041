"""
SinhaLM Context Improvement client — calls the Modal.com SinhaLM web endpoint.
Sends full-page OCR text, receives contextually corrected Sinhala text.

The Modal endpoint (sinhalm_agent_app.py) returns:
  POST /  -> {"improved_text": "..."}   (improve_context endpoint)
  POST /validate -> {"corrected_text": "..."}  (legacy validate endpoint)
"""

import httpx
from app.core.config import settings

TIMEOUT = 300.0  # Large LLM inference can take some time if cold starting


async def validate_text(raw_text: str) -> str:
    """
    Send full-page OCR text to SinhaLM for contextual correction.

    Returns the improved text, or raw_text unchanged if the service is
    not configured or returns an unexpected response.
    """
    if not raw_text or not raw_text.strip():
        return ""

    url = settings.sinhalm_modal_url
    if not url:
        return raw_text

    payload = {"raw_text": raw_text}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()
    # Primary key returned by sinhalm_agent_app.py improve_context endpoint
    # Fall back to legacy "corrected_text" key and then to raw_text
    return data.get("improved_text") or data.get("corrected_text") or raw_text
