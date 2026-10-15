"""Opt-in hosted STT. No automatic retries or fallback to another paid provider."""
import asyncio
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import time

from fastapi import HTTPException
import httpx
from app.core.config import get_settings

_http = httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5))
_codes = {"english": "en", "tamil": "ta", "sinhala": "si"}


async def audio_duration(content):
    # Probe before sending: duration controls the local quota, including malformed uploads.
    with tempfile.TemporaryDirectory(prefix="voicelearn-stt-") as folder:
        path = Path(folder) / "recording"
        path.write_bytes(content)
        try:
            process = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        except OSError as exc:
            raise HTTPException(503, "Audio validation is unavailable. Please try again later.") from exc
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            process.kill(); await process.communicate()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise HTTPException(422, "Could not read this recording. Please record it again.") from exc
        try:
            seconds = float(json.loads(output)["format"]["duration"])
            if process.returncode or not math.isfinite(seconds) or not 0 < seconds <= 60:
                raise ValueError()
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, "For fast transcription, use a valid recording of up to 60 seconds.") from exc
        return seconds


def reserve_quota(settings, seconds):
    path = Path(settings.groq_stt_quota_path or str(Path(settings.actions_store_path).parent / "groq-stt-quota.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    with sqlite3.connect(path, timeout=5) as db:
        db.execute("CREATE TABLE IF NOT EXISTS requests (created REAL NOT NULL, seconds REAL NOT NULL)")
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM requests WHERE created < ?", (now - 86400,))
        daily, total = db.execute("SELECT COUNT(*), COALESCE(SUM(seconds), 0) FROM requests").fetchone()
        minute = db.execute("SELECT COUNT(*) FROM requests WHERE created >= ?", (now - 60,)).fetchone()[0]
        if minute >= settings.groq_stt_requests_per_minute or daily >= settings.groq_stt_requests_per_day or total + max(10, seconds) > 6000:
            raise HTTPException(429, "Fast transcription's shared usage limit has been reached. Wait and retry, or type your command. No fallback service was called.")
        db.execute("INSERT INTO requests VALUES (?, ?)", (now, max(10, seconds)))


async def transcribe(content, filename, language):
    settings = get_settings()
    key = settings.groq_api_key.get_secret_value()
    if not key:
        raise HTTPException(503, "Fast transcription is not configured. Type your command or ask the administrator to configure the service.")
    seconds = await audio_duration(content)
    try:
        await asyncio.to_thread(reserve_quota, settings, seconds)
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(503, "Transcription usage could not be checked. Please retry later.") from exc
    try:
        response = await _http.post("https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": "Bearer " + key},
            files={"file": (Path(filename).name, content)},
            data={"model": settings.groq_stt_model, "language": _codes[language], "response_format": "verbose_json", "temperature": "0"})
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Transcription timed out. Retry or type your command. No fallback service was called.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Transcription could not connect. Retry or type your command.") from exc
    if response.status_code == 429:
        raise HTTPException(429, "The transcription service's quota is currently exhausted. Wait and retry, or type your command. No fallback service was called.")
    if response.status_code >= 400:
        raise HTTPException(503, "Fast transcription is currently unavailable. Retry later or type your command.")
    try:
        value = response.json()
        text = value["text"].strip()
        if not text or len(text) > 12000:
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(422, "No clear speech was recognized. Please record again or type your command.") from exc
    return {"transcript": text, "detected_language": _codes.get(str(value.get("language", "")).lower(), _codes[language]),
            "duration_ms": round(seconds * 1000), "engine": "groq/" + settings.groq_stt_model, "fallback_used": False}
