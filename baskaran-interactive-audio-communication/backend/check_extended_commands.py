"""Opt-in live command checks against a specifically selected local document.

Uses real configured OpenClaw/Modal services. Does not print source or transcript.
"""
import argparse
import asyncio
import io
import json
import time
import wave
from pathlib import Path
from uuid import uuid4

import httpx


async def main(document_id, provider, only_flashcards=False):
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        response = await client.get("/api/v1/actions/saved")
        response.raise_for_status()
        saved = response.json()
        source = next((item for item in saved if item["document_id"] == document_id and item["revision_mode"] == "sectioned"), None)
        if not source:
            raise ValueError("Create a sectioned revision for the selected document first.")
        commands = [
            "Create a one-minute audio revision and save it",
            "Create a detailed audio revision and save it",
            "Create an audio revision in Tamil and save it",
            "Create an audio revision in Sinhala and save it",
            "Create an audio revision in English and save it",
            "Create an audio revision of this section only and save it",
            "Create flashcards from this document and save them",
        ]
        if only_flashcards:
            commands = commands[-1:]
        # Bound concurrency: two independent workflows use existing services.
        semaphore = asyncio.Semaphore(2)
        async def check(command):
            async with semaphore:
                started = time.monotonic()
                body = {"command": command, "document_id": document_id, "session_id": str(uuid4()),
                        "language": "english", "revision_mode": "single", "provider": provider}
                if "this section only" in command:
                    body.update(source_action_id=source["action_id"], section_id=1)
                response = await client.post("/api/v1/actions", json=body)
                response.raise_for_status()
                ticket = response.json()["action_id"]
                print(f"Started: {command}", flush=True)
                deadline = time.monotonic() + 1920
                while time.monotonic() < deadline:
                    response = await client.get(f"/api/v1/actions/{ticket}")
                    response.raise_for_status()
                    value = response.json()
                    if value["status"] in {"complete", "partial", "failed"}:
                        break
                    await asyncio.sleep(4)
                evidence = {"command": command, "status": value["status"], "language": value["language"], "provider": value["provider"],
                            "saved": value["saved"], "error": value.get("error"),
                            "tools": list(dict.fromkeys(value["trace"])), "seconds": round(time.monotonic() - started, 1)}
                if value["status"] == "complete":
                    download = await client.get(f"/api/v1/actions/{ticket}/download")
                    download.raise_for_status()
                    assert download.content
                    evidence["download_verified"] = True
                    if value["intent"] == "flashcards":
                        assert download.json()["cards"] == value["flashcards"]
                        evidence["cards"] = len(value["flashcards"])
                    else:
                        audio = await client.get(f"/api/v1/actions/{ticket}/audio")
                        audio.raise_for_status()
                        with wave.open(io.BytesIO(audio.content)) as wav:
                            duration = wav.getnframes() / wav.getframerate()
                        assert abs(duration - value["audio_duration"]) < 0.01 and value["audio_saved"]
                        evidence["audio_seconds"] = round(duration, 2)
                        evidence["section_count"] = len(value.get("sections", []))
                        if "this section only" in command:
                            assert len(value["sections"]) == 1
                            passage = await client.get(f"/api/v1/actions/{ticket}/sections/0/source")
                            passage.raise_for_status()
                            assert passage.json()["excerpt"]
                        if "one-minute" in command:
                            assert value["target_duration"] == 60 and value["revision_mode"] == "single"
                print(json.dumps(evidence), flush=True)
                return evidence
        results = await asyncio.gather(*(check(command) for command in commands))
        suffix = "-flashcards" if only_flashcards else ""
        Path(f".actions-runtime/extended-command-check-{provider}{suffix}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        if any(result["status"] != "complete" for result in results):
            raise ValueError("One or more live commands failed; see recorded evidence.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--provider", choices=["direct", "openclaw_mcp"], default="openclaw_mcp")
    parser.add_argument("--only-flashcards", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.document_id, args.provider, args.only_flashcards))
