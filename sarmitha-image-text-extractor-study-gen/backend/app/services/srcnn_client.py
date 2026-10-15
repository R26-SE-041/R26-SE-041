"""
SRCNN client — calls the Modal.com SRCNN web endpoint.
Sends base64-encoded image, receives base64-encoded enhanced image.
"""

import asyncio
import base64
import httpx

from app.core.config import settings
from app.core.http import modal_client

TIMEOUT = 120.0  # SRCNN inference + network round-trip
MAX_CONNECT_ATTEMPTS = 3


async def enhance_image(image_bytes: bytes) -> bytes:
    """
    Send raw image bytes to the Modal SRCNN endpoint.
    Returns enhanced PNG bytes.

    Raises:
        ValueError: if Modal URL not configured.
        httpx.HTTPStatusError: on 4xx/5xx from Modal.
    """
    url = settings.srcnn_modal_url
    if not url:
        raise ValueError(
            "SRCNN_MODAL_URL is not set. "
            "Deploy modal_functions/srcnn_app.py and add the URL to .env"
        )

    payload = {"image_b64": base64.b64encode(image_bytes).decode("utf-8")}

    for attempt in range(MAX_CONNECT_ATTEMPTS):
        try:
            async with modal_client(TIMEOUT) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            break
        except httpx.ConnectError:
            if attempt == MAX_CONNECT_ATTEMPTS - 1:
                raise
            await asyncio.sleep(0.5 * (2**attempt))

    enhanced_b64: str = response.json()["enhanced_b64"]
    return base64.b64decode(enhanced_b64)
