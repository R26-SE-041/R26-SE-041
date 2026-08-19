"""Unit tests for language-specific ASR routing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.modal_client import call_whisper


@pytest.mark.asyncio
async def test_sinhala_routes_to_finetuned_small_model():
    settings = SimpleNamespace(modal_sinhala_asr_url="https://sinhala-asr.test")
    sinhala_result = {
        "text": "සිංහල පිටපත",
        "duration_seconds": 1.25,
        "engine": "Lingalingeswaran/whisper-small-sinhala",
    }

    with (
        patch("app.services.modal_client.get_settings", return_value=settings),
        patch(
            "app.services.modal_client.call_sinhala_asr_direct",
            new_callable=AsyncMock,
            return_value=sinhala_result,
        ) as sinhala_asr,
        patch("app.services.modal_client._http.post", new_callable=AsyncMock) as generic_whisper,
    ):
        result = await call_whisper(b"audio", "sample.webm", "sinhala")

    assert result == {
        "transcript": "සිංහල පිටපත",
        "detected_language": "si",
        "duration_ms": 1250,
        "engine": "Lingalingeswaran/whisper-small-sinhala",
    }
    sinhala_asr.assert_awaited_once_with(
        b"audio", "sample.webm", "application/octet-stream"
    )
    generic_whisper.assert_not_awaited()


@pytest.mark.asyncio
async def test_sinhala_does_not_fall_back_when_endpoint_is_missing():
    settings = SimpleNamespace(modal_sinhala_asr_url="")

    with patch("app.services.modal_client.get_settings", return_value=settings):
        with pytest.raises(RuntimeError, match="MODAL_SINHALA_ASR_URL"):
            await call_whisper(b"audio", "sample.webm", "sinhala")


@pytest.mark.asyncio
async def test_sinhala_does_not_fall_back_on_empty_transcript():
    settings = SimpleNamespace(
        modal_sinhala_asr_url="https://sinhala-asr.test",
    )

    with (
        patch("app.services.modal_client.get_settings", return_value=settings),
        patch(
            "app.services.modal_client.call_sinhala_asr_direct",
            new_callable=AsyncMock,
            return_value={"text": ""},
        ),
        patch(
            "app.services.modal_client._http.post",
            new_callable=AsyncMock,
        ) as generic_whisper,
    ):
        with pytest.raises(RuntimeError, match="No fallback model was used"):
            await call_whisper(b"audio", "sample.webm", "sinhala")

    generic_whisper.assert_not_awaited()
