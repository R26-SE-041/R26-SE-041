"""
Tests for /api/v1/voice/transcribe endpoint.
Modal client is mocked — tests don't require a real Modal deployment.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


MOCK_STT_RESULT = {
    "transcript": "What is Newton's second law?",
    "detected_language": "en",
    "duration_ms": 1200,
}

FAKE_AUDIO = b"RIFF" + b"\x00" * 100  # Minimal fake WAV header


# ── Helper ────────────────────────────────────────────────────────────────────

def _auth_headers():
    """Return a fake auth header (JWT verification is mocked)."""
    return {"Authorization": "Bearer fake-token"}


# ── Tests ─────────────────────────────────────────────────────────────────────

@patch("app.core.security.verify_token", return_value={"sub": "user-123"})
@patch("app.services.modal_client.call_whisper", new_callable=AsyncMock, return_value=MOCK_STT_RESULT)
def test_transcribe_english(mock_whisper, mock_verify, client):
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("test.webm", FAKE_AUDIO, "audio/webm")},
        data={"language": "english"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "What is Newton's second law?"
    assert body["selected_language"] == "english"
    assert body["detected_language"] == "en"
    mock_whisper.assert_called_once()


@patch("app.core.security.verify_token", return_value={"sub": "user-123"})
@patch("app.services.modal_client.call_whisper", new_callable=AsyncMock, return_value={**MOCK_STT_RESULT, "detected_language": "ta"})
def test_transcribe_tamil(mock_whisper, mock_verify, client):
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("test.webm", FAKE_AUDIO, "audio/webm")},
        data={"language": "tamil"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["selected_language"] == "tamil"


def test_transcribe_empty_audio(client):
    with patch("app.core.security.verify_token", return_value={"sub": "user-123"}):
        response = client.post(
            "/api/v1/voice/transcribe",
            files={"audio_file": ("test.webm", b"", "audio/webm")},
            data={"language": "english"},
            headers=_auth_headers(),
        )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_transcribe_unauthenticated(client):
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("test.webm", FAKE_AUDIO, "audio/webm")},
        data={"language": "english"},
    )
    assert response.status_code == 403  # No Bearer token


@patch("app.core.security.verify_token", return_value={"sub": "user-123"})
def test_transcribe_invalid_type(mock_verify, client):
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio_file": ("test.pdf", FAKE_AUDIO, "application/pdf")},
        data={"language": "english"},
        headers=_auth_headers(),
    )
    assert response.status_code == 415


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
