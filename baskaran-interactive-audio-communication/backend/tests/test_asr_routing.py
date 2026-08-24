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


@pytest.mark.asyncio
async def test_valid_tamil_qwen_result_does_not_call_whisper():
    settings = SimpleNamespace(
        modal_indic_stt_url="https://tamil-qwen.test",
        modal_whisper_url="https://whisper.test",
    )
    qwen_result = {
        "transcript": "நியூட்டனின் இரண்டாம் விதி",
        "detected_language": "ta",
        "duration_ms": 1200,
    }

    with (
        patch("app.services.modal_client.get_settings", return_value=settings),
        patch(
            "app.services.modal_client.call_indic_stt",
            new_callable=AsyncMock,
            return_value=qwen_result,
        ) as qwen,
        patch("app.services.modal_client._http.post", new_callable=AsyncMock) as whisper,
    ):
        result = await call_whisper(b"audio", "sample.webm", "tamil")

    assert result["transcript"] == "நியூட்டனின் இரண்டாம் விதி"
    assert result["fallback_used"] is False
    assert result["engine"] == "osmapi/tamil-asr-qwen3"
    qwen.assert_awaited_once_with(b"audio", "sample.webm")
    whisper.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_tamil_qwen_failure_still_falls_back_to_whisper():
    settings = SimpleNamespace(
        modal_indic_stt_url="https://tamil-qwen.test",
        modal_whisper_url="https://whisper.test",
        modal_token_id="",
        modal_token_secret="",
    )
    whisper_response = AsyncMock()
    whisper_response.raise_for_status = lambda: None
    whisper_response.json = lambda: {
        "transcript": "தமிழ் பதிப்பு",
        "detected_language": "ta",
        "duration_ms": 900,
    }

    with (
        patch("app.services.modal_client.get_settings", return_value=settings),
        patch(
            "app.services.modal_client.call_indic_stt",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Qwen service failed"),
        ),
        patch(
            "app.services.modal_client._http.post",
            new_callable=AsyncMock,
            return_value=whisper_response,
        ) as whisper,
    ):
        result = await call_whisper(b"audio", "sample.webm", "tamil")

    assert result["transcript"] == "தமிழ் பதிப்பு"
    assert result["fallback_used"] is True
    assert result["engine"] == "openai/whisper-large-v3"
    whisper.assert_awaited_once()
    assert whisper.await_args.kwargs["data"] == {"language_hint": "tamil"}
