"""Opt-in action API; existing Q&A endpoints are independent."""

import secrets
import json
import time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import get_current_user
from app.services import action_store as store, document_actions as service
from app.services.summary_text import clean_summary, plain_summary

router = APIRouter(prefix="/actions", tags=["actions"])


def enabled():
    if not get_settings().actions_enabled:
        raise HTTPException(404, "Document actions are disabled.")


def owner(request: Request, user: Annotated[dict | None, Depends(get_current_user)]):
    enabled()
    if user and user.get("sub"):
        return user["sub"]
    settings = get_settings()
    if (settings.actions_allow_local_guest and settings.chroma_host in {"localhost", "127.0.0.1", "local"}
            and request.client and request.client.host in {"127.0.0.1", "::1", "testclient"}):
        # Same shared 'guest' identity as existing local document uploads.
        return "guest"
    raise HTTPException(401, "Sign in to use document actions.")


class ActionRequest(BaseModel):
    command: str = Field(min_length=1, max_length=500)
    document_id: UUID
    session_id: UUID
    language: Literal["english", "tamil", "sinhala"] = "english"
    revision_mode: Literal["single", "sectioned"] = "single"


class ToolRequest(BaseModel):
    action_id: str = Field(min_length=20, max_length=100)


@router.get("/capabilities")
def capabilities():
    settings = get_settings()
    return {"enabled": settings.actions_enabled, "provider": settings.actions_provider,
            "max_document_chars": settings.actions_max_document_chars,
            "sectioned_enabled": getattr(settings, "actions_sectioned_enabled", False),
            "languages": ["english", "tamil", "sinhala"], "formats": ["pdf", "txt", "md"]}


@router.post("", status_code=202)
async def start_action(body: ActionRequest, tasks: BackgroundTasks, user_id: Annotated[str, Depends(owner)]):
    intent = service.classify(body.command)
    if not intent:
        raise HTTPException(422, "Command not recognized. Use one of the displayed command examples for your language.")
    if body.revision_mode == "sectioned" and intent == "audio_revision" and not getattr(get_settings(), "actions_sectioned_enabled", False):
        raise HTTPException(422, "Sectioned audio revision is disabled. Select Single audio.")
    document_id, session_id = str(body.document_id), str(body.session_id)
    try:
        await service.document_bytes(document_id, user_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    previous = store.latest(user_id, session_id, document_id, body.language) if intent == "save" else None
    if intent == "save" and not previous:
        raise HTTPException(409, "Generate a summary for this document in the selected language first.")
    ticket = store.create(user_id, session_id, document_id, intent, previous, body.language, body.revision_mode if intent == "audio_revision" else "single")
    tasks.add_task(service.run_action, ticket)
    return {"action_id": ticket}


def owned(action_id, user_id):
    try:
        action = store.get(action_id, user_id)
    except ValueError as exc:
        raise HTTPException(404, "Action not found.") from exc
    if action["expires"] < time.time() and action["status"] not in {"complete", "partial", "failed"}:
        store.update(action_id, status="partial" if action["summary"] else "failed",
                     error="Action expired before completion. Please retry.")
        action = store.get(action_id, user_id)
    return action


@router.get("/{action_id}")
def action_status(action_id: str, user_id: Annotated[str, Depends(owner)]):
    action = owned(action_id, user_id)
    saved = bool(action["saved"] and action["summary_id"] and store.artifact(action["summary_id"]).is_file())
    audio_ready = bool(action.get("audio_id") and store.artifact(action["audio_id"], "wav").is_file())
    language = action.get("language", "english")
    confirmation = {"english": "Your summary is ready.", "tamil": "உங்கள் சுருக்கம் தயாராக உள்ளது.",
                    "sinhala": "ඔබගේ සාරාංශය සූදානම්."}[language]
    if saved:
        confirmation = {"english": "Your summary is ready and saved.", "tamil": "உங்கள் சுருக்கம் தயாராகி சேமிக்கப்பட்டுள்ளது.",
                        "sinhala": "ඔබගේ සාරාංශය සූදානම් කර සුරකින ලදී."}[language]
    return {"action_id": action_id, "status": action["status"], "summary": clean_summary(action["summary"]) if action["summary"] else None,
            "saved": saved, "error": action["error"], "provider": action.get("provider"),
            "filename": ("lecture-revision.txt" if action["intent"] == "audio_revision" else "lecture-summary.txt") if saved else None,
            "download_path": f"/api/v1/actions/{action_id}/download" if saved else None,
            "intent": action["intent"], "trace": action["trace"],
            "revision_mode": action.get("revision_mode", "single"), "progress": action.get("progress"),
            "sections": [{key: section.get(key) for key in
                         ("id", "title", "script", "script_language", "duration", "start_seconds", "end_seconds")}
                         for section in action.get("sections", [])],
            "audio_ready": audio_ready, "audio_saved": bool(action.get("audio_saved") and audio_ready),
            "audio_duration": action.get("audio_duration"),
            "language": language, "summary_language": action.get("summary_language", "english"),
            "confirmation": ("Your audio revision is ready and saved." if action.get("audio_saved")
                             else confirmation)}



@router.post("/{action_id}/retry", status_code=202)
async def retry_audio(action_id: str, tasks: BackgroundTasks, user_id: Annotated[str, Depends(owner)]):
    """New ticket, same verified source/scripts; no translation regeneration."""
    import copy
    previous = owned(action_id, user_id)
    if not getattr(get_settings(), "actions_sectioned_enabled", False):
        raise HTTPException(422, "Sectioned audio revision is disabled.")
    sections = previous.get("sections", [])
    if (previous["status"] != "partial" or previous.get("revision_mode") != "sectioned"
            or not sections or "summarize_document" not in previous["trace"]
            or previous.get("summary_language") != previous.get("language")
            or any(s.get("script_language") != previous["language"] or not s.get("script") for s in sections)
            or service.section_transcript(sections) != previous["summary"]):
        raise HTTPException(409, "A complete prepared section transcript is required for audio retry.")
    try:
        filename, content = await service.document_bytes(previous["document_id"], user_id)
        source = service.extract(filename, content)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if service.revision_sections.source_hash(source) != previous.get("source_hash"):
        raise HTTPException(409, "The source document changed. Generate a new revision.")
    sections = copy.deepcopy(sections)
    for section in sections:
        if source[section["source_start"]:section["source_end"]] != section["source_text"]:
            raise HTTPException(409, "Source passage verification failed.")
        if section.get("audio_id"):
            try:
                _, durations = service.revision_sections.concatenate_wavs([store.artifact(section["audio_id"], "wav").read_bytes()])
                section["duration"] = durations[0]
            except (ValueError, OSError):
                section.update(audio_id=None, duration=None)
        section.pop("start_seconds", None); section.pop("end_seconds", None)
    ticket = store.create(user_id, previous["session_id"], previous["document_id"], "audio_revision",
                          previous, previous["language"], "sectioned")
    store.update(ticket, sections=sections, source_hash=previous["source_hash"], retry_of=action_id)
    tasks.add_task(service.run_action, ticket)
    return {"action_id": ticket}

@router.get("/{action_id}/download")
async def download(action_id: str, user_id: Annotated[str, Depends(owner)]):
    action = owned(action_id, user_id)
    transcript_only = action["intent"] == "audio_revision" and bool(action["summary"])
    if not transcript_only and (not action["saved"] or not action["summary_id"]):
        raise HTTPException(404, "No saved summary is available.")
    try:
        await service.document_bytes(action["document_id"], user_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if transcript_only:
        return Response(plain_summary(action["summary"]), media_type="text/plain", headers={
            "Content-Disposition": 'attachment; filename="lecture-revision.txt"'})
    path = store.artifact(action["summary_id"])
    if not path.is_file():
        raise HTTPException(404, "Saved summary file is unavailable.")
    # Older saved summaries also download cleanly without changing their records.
    return Response(plain_summary(path.read_text(encoding="utf-8")), media_type="text/plain",
                    headers={"Content-Disposition": 'attachment; filename="lecture-summary.txt"'})


@router.get("/{action_id}/audio")
async def revision_audio(action_id: str, user_id: Annotated[str, Depends(owner)]):
    action = owned(action_id, user_id)
    if not action.get("audio_id"):
        raise HTTPException(404, "No revision audio is available.")
    try:
        await service.document_bytes(action["document_id"], user_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    path = store.artifact(action["audio_id"], "wav")
    if not path.is_file():
        raise HTTPException(404, "Revision audio file is unavailable.")
    return Response(path.read_bytes(), media_type="audio/wav", headers={
        "Content-Disposition": 'attachment; filename="lecture-revision.wav"', "Cache-Control": "private, no-store"})



@router.get("/{action_id}/sections/{section_id}/source")
async def section_source(action_id: str, section_id: int, user_id: Annotated[str, Depends(owner)]):
    action = owned(action_id, user_id)
    sections = action.get("sections", [])
    if section_id < 0 or section_id >= len(sections):
        raise HTTPException(404, "Revision section not found.")
    try:
        filename, content = await service.document_bytes(action["document_id"], user_id)
        text = service.extract(filename, content)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if service.revision_sections.source_hash(text) != action.get("source_hash"):
        raise HTTPException(409, "The source document changed. Generate a new revision.")
    section = sections[section_id]
    excerpt = text[section["source_start"]:section["source_end"]]
    if excerpt != section["source_text"]:
        raise HTTPException(409, "The supporting source passage could not be verified.")
    return Response(json.dumps({"filename": filename, "excerpt": excerpt,
                    "start": section["source_start"], "end": section["source_end"],
                    "source_hash": action["source_hash"]}), media_type="application/json",
                    headers={"Cache-Control": "private, no-store"})

@router.post("/tools/{tool_name}")
async def bridge(tool_name: str, body: ToolRequest,
                 x_action_bridge_secret: Annotated[str | None, Header()] = None):
    enabled()
    secret = get_settings().actions_bridge_secret
    if not secret or not secrets.compare_digest(x_action_bridge_secret or "", secret):
        raise HTTPException(401, "Invalid tool bridge credentials.")
    try:
        return await service.execute_tool(tool_name, body.action_id)
    except ValueError as exc:
        try:
            action = store.get(body.action_id)
            if action["status"] not in {"complete", "partial", "failed"} and not action.get("error"):
                store.update(body.action_id, error=str(exc))
        except ValueError:
            pass
        raise HTTPException(409, str(exc)) from exc
