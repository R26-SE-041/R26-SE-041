"""Opt-in live audio revision check using an existing local guest document.

Calls the configured Gateway/model and existing Modal summary/TTS endpoints.
No credentials, document text or action tickets are printed.
"""

import asyncio
import argparse
from datetime import datetime
import io
import json
import time
import wave
from pathlib import Path
from uuid import uuid4

import httpx


SAMPLE_TEXT = (
    
    "A fictional biology classroom studied Blue Lake. They recorded three producers: "
    "algae, reeds and water lilies. Snails consumed algae. Fish consumed snails. "
    "The class used this food chain to discuss energy transfer.\n\nThey counted organisms "
    "in the same marked area each week, using the same method. After four weeks, "
    "they compared their observations. Counts alone did not establish why changes "
    "occurred. The teacher asked students to distinguish observations from explanations. "
    "\n\nThe lesson concluded that consistent sampling and clearly recorded observations "
    "help comparisons, while explanations require additional evidence."
)


async def main(sample, document_id, verify_sample=False, language="english", revision_mode="single", resume_sample=False):
    existing_ticket = None
    if verify_sample or resume_sample:
        from app.services import action_store as store, local_document_store
        with store.connection() as db:
            rows = db.execute("SELECT id,data,document_id FROM actions WHERE intent='audio_revision' AND user_id='guest' ORDER BY rowid DESC").fetchall()
        existing_ticket = next((row["id"] for row in rows
            if json.loads(row["data"]).get("language", "english") == language
            and json.loads(row["data"]).get("revision_mode", "single") == revision_mode
            and (local_document_store.get_document(row["document_id"], "guest") or {}).get("filename")
                == "audio-revision-test-sample.txt"), None)
        if not existing_ticket:
            raise ValueError("No generated sample run is available to verify.")
        if resume_sample:
            selected = store.get(existing_ticket, "guest")
            record = local_document_store.get_document(selected["document_id"], "guest")
            if not record or local_document_store.read_document(record) != SAMPLE_TEXT.encode():
                raise ValueError("Only the exact generated fictional sample can be resumed by this checker.")
    if sample:
        from app.services import local_document_store
        document_id = str(uuid4())
        local_document_store.save_document(document_id=document_id, user_id="guest",
            filename="audio-revision-test-sample.txt", file_type="txt", chunk_count=0,
            uploaded_at=datetime.now(), content=SAMPLE_TEXT.encode())
        print("Using a generated fictional test lecture; no user document content is selected.", flush=True)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        caps = await client.get("/api/v1/actions/capabilities")
        caps.raise_for_status()
        if caps.json().get("provider") != "openclaw_mcp":
            raise ValueError("Live check requires the OpenClaw provider.")
        started = time.monotonic()
        if existing_ticket:
            if resume_sample:
                response = await client.post(f"/api/v1/actions/{existing_ticket}/retry")
                response.raise_for_status()
                ticket = response.json()["action_id"]
            else:
                ticket = existing_ticket
        else:
            command = {"english": "Create a short audio revision of this document and save it",
                       "tamil": "இந்த ஆவணத்தின் ஒலி மீளாய்வை உருவாக்கி சேமிக்கவும்",
                       "sinhala": "මෙම ලේඛනයේ ශ්‍රව්‍ය පුනරාවලෝකනයක් සාදා සුරකින්න"}[language]
            response = await client.post("/api/v1/actions", json={
                "command": command,
                "document_id": document_id, "session_id": str(uuid4()), "language": language, "revision_mode": revision_mode})
            response.raise_for_status()
            ticket = response.json()["action_id"]
        previous = None
        while time.monotonic() - started < (1920 if revision_mode == "sectioned" else 720):
            status = await client.get(f"/api/v1/actions/{ticket}")
            status.raise_for_status()
            value = status.json()
            if value["status"] != previous:
                print("Audio revision: " + value["status"], flush=True)
                previous = value["status"]
            if value["status"] in {"complete", "partial", "failed"}:
                break
            await asyncio.sleep(3)
        else:
            raise ValueError("Live check timed out; inspect backend status.")
        expected = ["summarize_document", "create_revision_audio", "save_audio_revision"]
        if value["status"] != "complete" or not value["audio_saved"] or list(dict.fromkeys(value["trace"])) != expected:
            raise ValueError("Audio workflow did not complete with all three verified tools.")
        if value.get("summary_language", "english") != language:
            raise ValueError("Transcript is not in the requested language.")
        audio = await client.get(f"/api/v1/actions/{ticket}/audio")
        audio.raise_for_status()
        transcript = await client.get(f"/api/v1/actions/{ticket}/download")
        transcript.raise_for_status()
        if transcript.text != value["summary"]:
            raise ValueError("Downloaded transcript differs from the spoken script.")
        with wave.open(io.BytesIO(audio.content), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
            if abs(duration - value["audio_duration"]) > 0.01 or not wav.readframes(wav.getnframes()):
                raise ValueError("Downloaded WAV verification failed.")
        if revision_mode == "sectioned":
            from app.services import document_actions, action_store
            document_actions.verify_section_manifest(action_store.get(ticket, "guest"))
            sections = value.get("sections", [])
            if not 1 <= len(sections) <= 3:
                raise ValueError("Section count verification failed.")
            offset = 0.0
            for section in sections:
                if section["start_seconds"] != offset or section["duration"] <= 0:
                    raise ValueError("Section timing verification failed.")
                offset = section["end_seconds"]
                source = await client.get(f"/api/v1/actions/{ticket}/sections/{section['id']}/source")
                source.raise_for_status()
                if not source.json()["excerpt"]:
                    raise ValueError("Supporting source passage is empty.")
            if abs(offset - duration) > 0.01:
                raise ValueError("Combined section duration mismatch.")
        evidence = {"revision_mode": revision_mode, "section_count": len(value.get("sections", [])), "language": language, "provider": value["provider"], "status": value["status"], "trace": value["trace"],
                    "audio_duration_seconds": round(duration, 2), "audio_bytes": len(audio.content),
                    "transcript_words": len(transcript.text.split()),
                    "resume_elapsed_seconds" if resume_sample else "verification_seconds" if existing_ticket else "elapsed_seconds": round(time.monotonic() - started, 2),
                    "transcript_download_verified": True, "wav_download_verified": True,
                    "section_sources_verified": revision_mode == "sectioned",
                    "section_timings_verified": revision_mode == "sectioned"}
        suffix = "-resumed" if resume_sample else "-verified" if existing_ticket else ""
        target = Path(__file__).with_name(".actions-runtime") / f"audio-revision-check-{language}-{revision_mode}{suffix}.json"
        target.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--sample", action="store_true", help="Create and use a fictional local guest test lecture")
    choice.add_argument("--document-id", type=str, help="Explicitly select an existing local guest document")
    choice.add_argument("--verify-latest-sample", action="store_true", help="Verify downloads from the generated sample without any new generation calls")
    choice.add_argument("--retry-latest-sample", action="store_true", help="Retry audio from the exact generated sample transcript; no new source/translation generation")
    parser.add_argument("--language", choices=["english", "tamil", "sinhala"], default="english")
    parser.add_argument("--revision-mode", choices=["single", "sectioned"], default="single")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.sample, args.document_id, args.verify_latest_sample, args.language, args.revision_mode, args.retry_latest_sample))
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"Live check failed (HTTP {exc.response.status_code}); verify backend/Gateway configuration.")
    except httpx.HTTPError as exc:
        raise SystemExit(f"Live check failed ({type(exc).__name__}); verify backend/Gateway connectivity.")
    except ValueError as exc:
        raise SystemExit(str(exc))
