"""Action execution, ownership, partial failure and agent-result verification."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes import actions
from app.core.security import get_current_user
from app.services import action_store as store, document_actions as service, local_document_store


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = SimpleNamespace(actions_enabled=True, actions_allow_local_guest=False,
        actions_provider="direct", actions_store_path=str(tmp_path / "actions"),
        local_document_store_path=str(tmp_path / "documents"), actions_timeout_seconds=60,
        actions_max_document_chars=12000, actions_bridge_secret="bridge-test-secret",
        chroma_host="local", openclaw_gateway_token="", openclaw_gateway_url="http://127.0.0.1:18789",
        openclaw_agent_id="voicelearn-actions")
    for module in (actions, store, service, local_document_store):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    document = str(uuid4())
    local_document_store.save_document(document_id=document, user_id="alice", filename="lecture.txt",
        file_type="txt", chunk_count=1, uploaded_at=datetime.now(), content=b"Lecture about normalization.")
    monkeypatch.setattr(service, "generate_summary", AsyncMock(return_value="Normalization reduces duplication."))
    app = FastAPI()
    app.include_router(actions.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: {"sub": "alice"}
    return settings, document, str(uuid4()), app


@pytest.mark.parametrize("text,intent", [
    ("Summarize this document", "summarize"),
    ("Please summarize the selected PDF and save it.", "summarize_and_save"),
    ("Save the summary as a text file", "save"),
    ("What does save mean in this lecture?", None),
    ("Explain normalization", None),
    ("Summarize this document and email it", None),
])
def test_intents(text, intent):
    assert service.classify(text) == intent


def start(client, doc, session, command):
    response = client.post("/api/v1/actions", json={"command": command, "document_id": doc, "session_id": session})
    assert response.status_code == 202, response.text
    return response.json()["action_id"]


def test_combined_action_actual_file_and_owner_isolation(env):
    _, doc, session, app = env
    with TestClient(app) as client:
        ticket = start(client, doc, session, "Summarize this document and save it")
        response = client.get(f"/api/v1/actions/{ticket}").json()
        assert response["status"] == "complete" and response["saved"]
        downloaded = client.get(f"/api/v1/actions/{ticket}/download")
        assert downloaded.status_code == 200
        assert downloaded.text == response["summary"]
        app.dependency_overrides[get_current_user] = lambda: {"sub": "bob"}
        assert client.get(f"/api/v1/actions/{ticket}").status_code == 404
        assert client.get(f"/api/v1/actions/{ticket}/download").status_code == 404
        assert client.post("/api/v1/actions", json={"command": "Summarize this document",
            "document_id": doc, "session_id": session}).status_code == 404


def test_save_later_uses_same_session_and_document(env):
    _, doc, session, app = env
    with TestClient(app) as client:
        first = start(client, doc, session, "Summarize this document")
        second = start(client, doc, session, "Save the summary")
        assert store.get(first)["summary_id"] == store.get(second)["summary_id"]
        assert store.get(second)["trace"] == ["save_summary"]
        assert client.post("/api/v1/actions", json={"command": "Save the summary",
            "document_id": doc, "session_id": str(uuid4())}).status_code == 409


def test_failed_save_preserves_summary(env, monkeypatch):
    _, doc, session, app = env
    monkeypatch.setattr(store, "artifact", lambda _: (_ for _ in ()).throw(OSError("disk unavailable")))
    with TestClient(app) as client:
        ticket = start(client, doc, session, "Summarize this document and save it")
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["status"] == "partial" and value["summary"]
        assert not value["saved"] and value["error"]


def test_agent_prose_cannot_claim_success(env, monkeypatch):
    settings, doc, session, app = env
    settings.actions_provider = "openclaw_mcp"
    monkeypatch.setattr(service, "run_openclaw", AsyncMock(return_value="Saved successfully"))
    with TestClient(app) as client:
        ticket = start(client, doc, session, "Summarize this document and save it")
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["status"] == "failed" and not value["saved"]


def test_feature_flag_auth_and_bridge_guards(env):
    settings, doc, session, app = env
    with TestClient(app) as client:
        assert client.post("/api/v1/actions/tools/save_summary", json={"action_id": "x" * 32}).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: None
        assert client.post("/api/v1/actions", json={"command": "Summarize this document",
            "document_id": doc, "session_id": session}).status_code == 401
        settings.actions_enabled = False
        assert client.get("/api/v1/actions/capabilities").json()["enabled"] is False
        assert client.get("/api/v1/actions/unknown").status_code == 404


@pytest.mark.asyncio
async def test_ticket_scope_expiry_and_order(env):
    _, doc, session, _ = env
    import time
    ticket = store.create("alice", session, doc, "summarize_and_save")
    with pytest.raises(ValueError, match="Generate a summary"):
        await service.execute_tool("save_summary", ticket)
    summary_only = store.create("alice", session, doc, "summarize")
    with pytest.raises(ValueError, match="does not permit saving"):
        await service.execute_tool("save_summary", summary_only)
    with store.connection() as db:
        db.execute("UPDATE actions SET expires=? WHERE id=?", (time.time() - 1, ticket))
    with pytest.raises(ValueError, match="expired"):
        await service.execute_tool("summarize_document", ticket)


def test_document_size_and_empty_text(env):
    with pytest.raises(ValueError, match="limit"):
        service.extract("large.txt", b"a" * 12001)
    with pytest.raises(ValueError, match="no extractable text"):
        service.extract("empty.txt", b" ")


def test_bridge_authenticated_execution_and_closed_ticket(env):
    settings, doc, session, app = env
    ticket = store.create("alice", session, doc, "summarize_and_save")
    headers = {"X-Action-Bridge-Secret": settings.actions_bridge_secret}
    with TestClient(app) as client:
        summarized = client.post("/api/v1/actions/tools/summarize_document",
            json={"action_id": ticket}, headers=headers)
        assert summarized.status_code == 200
        assert "summary" not in summarized.json()
        saved = client.post("/api/v1/actions/tools/save_summary",
            json={"action_id": ticket}, headers=headers)
        assert saved.status_code == 200 and saved.json()["saved"]
        store.update(ticket, status="complete")
        assert client.post("/api/v1/actions/tools/save_summary",
            json={"action_id": ticket}, headers=headers).status_code == 409
        assert client.post("/api/v1/actions/tools/save_summary",
            json={"action_id": "x" * 32}, headers=headers).status_code == 409


@pytest.mark.asyncio
async def test_gateway_request_and_mcp_execution_verification(env, monkeypatch):
    import httpx
    settings, doc, session, _ = env
    settings.actions_provider = "openclaw_mcp"
    settings.openclaw_gateway_token = "test-token"
    ticket = store.create("alice", session, doc, "summarize_and_save")
    original_client = httpx.AsyncClient

    async def gateway(request):
        import json
        assert str(request.url) == "http://127.0.0.1:18789/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-token"
        payload = json.loads(request.content)
        assert payload["model"] == "openclaw/voicelearn-actions"
        assert ticket in payload["messages"][0]["content"]
        await service.execute_tool("summarize_document", ticket)
        await service.execute_tool("save_summary", ticket)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Done"}}]})

    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs:
        original_client(transport=httpx.MockTransport(gateway), **kwargs))
    await service.run_action(ticket)
    value = store.get(ticket)
    assert value["status"] == "complete" and value["saved"]
    assert value["trace"] == ["summarize_document", "save_summary"]


@pytest.mark.asyncio
async def test_timeout_reports_failure(env, monkeypatch):
    import asyncio
    _, doc, session, _ = env
    monkeypatch.setattr(service, "generate_summary", AsyncMock(side_effect=asyncio.TimeoutError))
    ticket = store.create("alice", session, doc, "summarize")
    await service.run_action(ticket)
    value = store.get(ticket)
    assert value["status"] == "failed" and value["error"] == "Action timed out."


def test_summary_cleanup_and_plain_export(env, monkeypatch):
    _, doc, session, app = env
    model_text = "thought\n**Document Summary**\n\n## Concepts\n* **Main point:** Keep `file_name` intact.\nA thought about dogs."
    monkeypatch.setattr(service, "generate_summary", AsyncMock(return_value=model_text))
    with TestClient(app) as client:
        ticket = start(client, doc, session, "Summarize this document and save it")
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["summary"].startswith("**Document Summary**")
        expected = "Document Summary\n\nConcepts\n- Main point: Keep file_name intact.\nA thought about dogs."
        assert store.artifact(store.get(ticket)["summary_id"]).read_text(encoding="utf-8") == expected
        assert client.get(f"/api/v1/actions/{ticket}/download").text == expected


def test_existing_artifact_download_is_cleaned(env):
    _, doc, session, app = env
    ticket = store.create("alice", session, doc, "summarize_and_save")
    summary_id = uuid4().hex
    raw = "thought\n**Old summary**\n* **Fact:** Dogs communicate."
    store.artifact(summary_id).write_text(raw, encoding="utf-8")
    store.update(ticket, status="complete", summary=raw, summary_id=summary_id, saved=True)
    with TestClient(app) as client:
        assert client.get(f"/api/v1/actions/{ticket}").json()["summary"].startswith("**Old summary**")
        assert client.get(f"/api/v1/actions/{ticket}/download").text == "Old summary\n- Fact: Dogs communicate."


def test_reasoning_block_removal_preserves_summary():
    from app.services.summary_text import clean_summary
    assert clean_summary("<think>Internal reasoning</think>\n**Summary**\nUseful content.") == "**Summary**\nUseful content."


def revision_wav():
    import io
    import wave
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\0\0" * 24000)
    return buffer.getvalue()


@pytest.mark.parametrize("command", ["Create a short audio revision of this document and save it",
    "Please create an audio revision of the selected PDF."])
def test_audio_revision_artifacts_and_owner(env, monkeypatch, command):
    _, doc, session, app = env
    from app.services import modal_client
    script = "Let us review normalization. It reduces duplication. That is the main idea."
    monkeypatch.setattr(service, "generate_audio_script", AsyncMock(return_value=script))
    tts = AsyncMock(return_value=revision_wav())
    monkeypatch.setattr(modal_client, "call_english_tts", tts)
    with TestClient(app) as client:
        ticket = start(client, doc, session, command)
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["status"] == "complete" and value["audio_saved"]
        assert value["audio_duration"] == 1
        assert value["trace"] == ["summarize_document", "create_revision_audio", "save_audio_revision"]
        assert client.get(f"/api/v1/actions/{ticket}/audio").content == revision_wav()
        assert client.get(f"/api/v1/actions/{ticket}/download").text == script
        tts.assert_awaited_once_with(script)
        app.dependency_overrides[get_current_user] = lambda: {"sub": "bob"}
        assert client.get(f"/api/v1/actions/{ticket}/audio").status_code == 404


@pytest.mark.parametrize("audio", [None, b"not a wav", b"RIFF\0\0\0\0WAVE"])
def test_audio_failure_preserves_downloadable_transcript(env, monkeypatch, audio):
    _, doc, session, app = env
    from app.services import modal_client
    monkeypatch.setattr(service, "generate_audio_script", AsyncMock(return_value="A spoken revision."))
    monkeypatch.setattr(modal_client, "call_english_tts", AsyncMock(return_value=audio))
    with TestClient(app) as client:
        ticket = start(client, doc, session, "Create an audio revision of this document")
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["status"] == "partial" and not value["audio_saved"]
        assert value["trace"] == ["summarize_document"]
        assert client.get(f"/api/v1/actions/{ticket}/download").text == "A spoken revision."
        assert client.get(f"/api/v1/actions/{ticket}/audio").status_code == 404


@pytest.mark.asyncio
async def test_audio_tools_require_scope_and_order(env):
    _, doc, session, _ = env
    ordinary = store.create("alice", session, doc, "summarize")
    with pytest.raises(ValueError, match="does not permit audio"):
        await service.execute_tool("create_revision_audio", ordinary)
    ticket = store.create("alice", session, doc, "audio_revision")
    with pytest.raises(ValueError, match="transcript before"):
        await service.execute_tool("create_revision_audio", ticket)
    store.update(ticket, summary="A revision.", summary_id=uuid4().hex, trace=["summarize_document"])
    with pytest.raises(ValueError, match="Generate audio before"):
        await service.execute_tool("save_audio_revision", ticket)
    with pytest.raises(ValueError, match="does not permit saving"):
        await service.execute_tool("save_summary", ticket)


@pytest.mark.asyncio
async def test_audio_expiry_during_tts_cannot_complete(env, monkeypatch):
    import time
    _, doc, session, _ = env
    ticket = store.create("alice", session, doc, "audio_revision")
    store.update(ticket, summary="Revision.", summary_id=uuid4().hex, trace=["summarize_document"])
    async def late_audio(script):
        with store.connection() as db:
            db.execute("UPDATE actions SET expires=? WHERE id=?", (time.time() - 1, ticket))
        return revision_wav(), 1
    monkeypatch.setattr(service, "synthesize_revision", late_audio)
    with pytest.raises(ValueError, match="expired while"):
        await service.execute_tool("create_revision_audio", ticket)
    assert store.get(ticket)["audio_id"] is None


@pytest.mark.parametrize("command,intent", [
    ("தயவுசெய்து இந்த ஆவணத்தை சுருக்கவும்.", "summarize"),
    ("சுருக்கத்தை சேமிக்கவும்", "save"),
    ("இந்த ஆவணத்தை சுருக்கி சேமிக்கவும்", "summarize_and_save"),
    ("இந்த ஆவணத்தின் ஒலி மீளாய்வை உருவாக்கி சேமிக்கவும்", "audio_revision"),
    ("කරුණාකර මෙම ලේඛනය සාරාංශ කරන්න.", "summarize"),
    ("සාරාංශය සුරකින්න", "save"),
    ("මෙම ලේඛනය සාරාංශ කර සුරකින්න", "summarize_and_save"),
    ("මෙම ලේඛනයේ ශ්‍රව්‍ය පුනරාවලෝකනයක් සාදා සුරකින්න", "audio_revision"),
    ("இந்த ஆவணத்தை மின்னஞ்சலில் அனுப்பவும்", None),
])
def test_native_command_scope(command, intent):
    assert service.classify(command) == intent


@pytest.mark.parametrize("language,native,tts_name", [
    ("tamil", "ஒரே முறையில் பதிவுகளை சேகரிப்பது ஒப்பீடுகளுக்கு உதவுகிறது.", "call_tamil_tts"),
    ("sinhala", "එකම ක්‍රමය භාවිතයෙන් නිරීක්ෂණ සටහන් කිරීම සැසඳීමට උපකාරී වේ.", "call_sinhala_vits_tts_direct"),
])
def test_native_audio_uses_scoped_language_and_existing_tts(env, monkeypatch, language, native, tts_name):
    _, doc, session, app = env
    from app.services import modal_client
    monkeypatch.setattr(service, "generate_audio_script", AsyncMock(return_value="Consistent records help comparisons."))
    monkeypatch.setattr(modal_client, "call_localizer", AsyncMock(return_value={"localized_text": native}))
    tts = AsyncMock(return_value=revision_wav())
    monkeypatch.setattr(modal_client, tts_name, tts)
    english = AsyncMock()
    monkeypatch.setattr(modal_client, "call_english_tts", english)
    with TestClient(app) as client:
        response = client.post("/api/v1/actions", json={"command": "Create an audio revision of this document",
            "document_id": doc, "session_id": session, "language": language})
        assert response.status_code == 202
        ticket = response.json()["action_id"]
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["status"] == "complete" and value["language"] == value["summary_language"] == language
        assert client.get(f"/api/v1/actions/{ticket}/download").text == native
        tts.assert_awaited_once_with(native)
        english.assert_not_awaited()


def test_localization_failure_cannot_report_native_success(env, monkeypatch):
    _, doc, session, app = env
    from app.services import modal_client
    monkeypatch.setattr(service, "generate_audio_script", AsyncMock(return_value="English source revision."))
    monkeypatch.setattr(modal_client, "call_localizer", AsyncMock(return_value={"localized_text": "English fallback."}))
    monkeypatch.setattr(modal_client, "call_answer_generator", AsyncMock(return_value={"answer": "Still English."}))
    tts = AsyncMock()
    monkeypatch.setattr(modal_client, "call_tamil_tts", tts)
    with TestClient(app) as client:
        response = client.post("/api/v1/actions", json={"command": "Create an audio revision of this document",
            "document_id": doc, "session_id": session, "language": "tamil"})
        value = client.get('/api/v1/actions/' + response.json()["action_id"]).json()
        assert value["status"] == "partial" and value["summary_language"] == "english"
        assert not value["audio_ready"] and value["error"]
        tts.assert_not_awaited()


def test_save_previous_is_language_scoped(env):
    _, doc, session, app = env
    with TestClient(app) as client:
        start(client, doc, session, "Summarize this document")
        response = client.post("/api/v1/actions", json={"command": "சுருக்கத்தை சேமிக்கவும்",
            "document_id": doc, "session_id": session, "language": "tamil"})
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_native_rewrite_uses_selected_model_language(env, monkeypatch):
    from app.services import modal_client
    monkeypatch.setattr(modal_client, "call_localizer", AsyncMock(return_value={"localized_text": "Blue Lake பற்றிய பாடம்."}))
    rewrite = AsyncMock(return_value={"answer": "ப்ளூ ஏரி பற்றிய பாடம்."})
    monkeypatch.setattr(modal_client, "call_answer_generator", rewrite)
    assert await service.localize_action_text("A lesson about Blue Lake.", "tamil") == "ப்ளூ ஏரி பற்றிய பாடம்."
    assert rewrite.await_args.args[1] == "tamil"
    assert rewrite.await_args.kwargs["context_chunks"] == ["Blue Lake பற்றிய பாடம்."]


@pytest.mark.asyncio
async def test_mcp_translation_failure_retains_specific_error(env, monkeypatch):
    settings, doc, session, app = env
    settings.actions_provider = "openclaw_mcp"
    ticket = store.create("alice", session, doc, "audio_revision", language="tamil")
    monkeypatch.setattr(service, "generate_audio_script", AsyncMock(return_value="English source."))
    monkeypatch.setattr(service, "localize_action_text", AsyncMock(side_effect=ValueError("Native transcript preparation failed.")))
    with TestClient(app) as client:
        result = client.post('/api/v1/actions/tools/summarize_document',
            json={"action_id": ticket}, headers={"X-Action-Bridge-Secret": settings.actions_bridge_secret})
        assert result.status_code == 409
    monkeypatch.setattr(service, "run_openclaw", AsyncMock(return_value="Done"))
    await service.run_action(ticket)
    value = store.get(ticket)
    assert value["status"] == "partial" and value["summary_language"] == "english"
    assert value["error"] == "Native transcript preparation failed."


# Sectioned revision extends audio actions, while the baseline remains unchanged.
from app.services import revision_sections


@pytest.mark.parametrize("text", ["One paragraph.", "First.\n\nSecond.\n\nThird.\n\nFourth.", "Heading\nText.\n\nNext paragraph."])
def test_source_spans_cover_exact_original_paragraphs(text):
    spans = revision_sections.split_source(text)
    assert 1 <= len(spans) <= 3
    assert spans[0]["source_start"] == 0 and spans[-1]["source_end"] == len(text)
    for i, span in enumerate(spans):
        assert span["id"] == i
        assert text[span["source_start"]:span["source_end"]] == span["source_text"]
        if i:
            assert spans[i - 1]["source_end"] <= span["source_start"]


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ['not json', '{"sections": []}', '{"sections": [{"id": 7,"title":"Title","script":"Text"}]}'])
async def test_invalid_section_generation_rejected(monkeypatch, answer):
    from app.services import modal_client
    monkeypatch.setattr(modal_client, "call_answer_generator", AsyncMock(return_value={"answer": answer}))
    with pytest.raises(ValueError, match="invalid structured"):
        await revision_sections.generate_sections("One paragraph.")


@pytest.mark.asyncio
async def test_structured_generation_uses_bounded_source_spans(monkeypatch):
    from app.services import modal_client
    import json
    response = {"sections": [{"id": i, "title": f"Topic {i}", "script": f"Revision {i}."} for i in range(3)]}
    model = AsyncMock(return_value={"answer": json.dumps(response)})
    monkeypatch.setattr(modal_client, "call_answer_generator", model)
    sections = await revision_sections.generate_sections("A.\n\nB.\n\nC.")
    assert [s["source_text"] for s in sections] == ["A.", "B.", "C."]
    assert "SOURCE SECTION 2" in model.call_args.kwargs["context_chunks"][0]
    assert model.await_count == 1


def section_fixture(env, monkeypatch):
    settings, doc, session, app = env
    settings.actions_sectioned_enabled = True
    settings.actions_sectioned_timeout_seconds = 1800
    text = "First topic.\n\nSecond topic.\n\nThird topic."
    local_document_store.save_document(document_id=doc, user_id="alice", filename="lecture.txt",
        file_type="txt", chunk_count=1, uploaded_at=datetime.now(), content=text.encode())
    sections = [{**s, "title": f"Topic {s['id'] + 1}", "script": s["source_text"],
                 "script_language": "english", "audio_id": None, "duration": None}
                for s in revision_sections.split_source(text)]
    generator = AsyncMock(return_value=sections)
    monkeypatch.setattr(revision_sections, "generate_sections", generator)
    tts = AsyncMock(return_value=(revision_wav(), 1))
    monkeypatch.setattr(service, "synthesize_revision", tts)
    return doc, session, app, generator, tts


@pytest.mark.parametrize("language", ["english", "tamil", "sinhala"])
def test_sectioned_workflow_timings_source_and_downloads(env, monkeypatch, language):
    doc, session, app, generator, tts = section_fixture(env, monkeypatch)
    native = {"tamil": "முதல் பகுதி.", "sinhala": "පළමු කොටස."}
    localizer = AsyncMock(return_value=native.get(language, ""))
    monkeypatch.setattr(service, "localize_action_text", localizer)
    with TestClient(app) as client:
        response = client.post("/api/v1/actions", json={"command": "Create an audio revision of this document",
            "document_id": doc, "session_id": session, "language": language, "revision_mode": "sectioned"})
        assert response.status_code == 202
        ticket = response.json()["action_id"]
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["status"] == "complete" and value["audio_saved"]
        assert value["revision_mode"] == "sectioned" and value["audio_duration"] == 3
        assert [s["start_seconds"] for s in value["sections"]] == [0, 1, 2]
        assert [s["end_seconds"] for s in value["sections"]] == [1, 2, 3]
        assert "source_text" not in value["sections"][0]
        assert client.get(f"/api/v1/actions/{ticket}/download").text == value["summary"]
        source = client.get(f"/api/v1/actions/{ticket}/sections/1/source")
        assert source.status_code == 200 and source.json()["excerpt"] == "Second topic."
        assert source.headers["cache-control"] == "private, no-store"
        with __import__("wave").open(__import__("io").BytesIO(client.get(f"/api/v1/actions/{ticket}/audio").content)) as wav:
            assert wav.getnframes() == 72000
        service.verify_section_manifest(store.get(ticket))
        assert tts.await_count == 3 and generator.await_count == 1
        if language != "english":
            assert localizer.await_count == 3
            assert all(call.args[1] == language for call in tts.call_args_list)
        assert client.get(f"/api/v1/actions/{ticket}/sections/-1/source").status_code == 404
        app.dependency_overrides[get_current_user] = lambda: {"sub": "bob"}
        assert client.get(f"/api/v1/actions/{ticket}/sections/0/source").status_code == 404
        app.dependency_overrides[get_current_user] = lambda: {"sub": "alice"}
        local_document_store.save_document(document_id=doc, user_id="alice", filename="lecture.txt",
            file_type="txt", chunk_count=1, uploaded_at=datetime.now(), content=b"Changed document.")
        assert client.get(f"/api/v1/actions/{ticket}/sections/0/source").status_code == 409


def test_section_tts_failure_preserves_script_without_claiming_audio(env, monkeypatch):
    doc, session, app, _, tts = section_fixture(env, monkeypatch)
    tts.side_effect = [(revision_wav(), 1), ValueError("Speech unavailable.")]
    with TestClient(app) as client:
        ticket = client.post("/api/v1/actions", json={"command": "Create an audio revision of this document",
            "document_id": doc, "session_id": session, "revision_mode": "sectioned"}).json()["action_id"]
        value = client.get(f"/api/v1/actions/{ticket}").json()
        assert value["status"] == "partial" and not value["audio_saved"] and not value["audio_ready"]
        assert len(value["sections"]) == 3 and value["summary"]
        assert client.get(f"/api/v1/actions/{ticket}/download").status_code == 200
        assert store.get(ticket)["sections"][0]["audio_id"]


@pytest.mark.asyncio
async def test_section_tools_are_idempotent_and_manifest_tampering_rejected(env, monkeypatch):
    doc, session, _, generator, tts = section_fixture(env, monkeypatch)
    ticket = store.create("alice", session, doc, "audio_revision", revision_mode="sectioned")
    for tool in ["summarize_document", "summarize_document", "create_revision_audio", "create_revision_audio", "save_audio_revision"]:
        result = await service.execute_tool(tool, ticket)
        assert "sections" not in result and "source_text" not in result and "summary" not in result
    assert generator.await_count == 1 and tts.await_count == 3
    action = store.get(ticket)
    action["sections"][0]["duration"] = 99
    with pytest.raises(ValueError, match="manifest verification"):
        service.verify_section_manifest(action)


def test_section_feature_flag_and_mode_validation(env):
    _, doc, session, app = env
    with TestClient(app) as client:
        payload = {"command": "Create an audio revision of this document", "document_id": doc,
                   "session_id": session, "revision_mode": "sectioned"}
        assert client.post("/api/v1/actions", json=payload).status_code == 422
        payload["revision_mode"] = "unknown"
        assert client.post("/api/v1/actions", json=payload).status_code == 422


def test_wav_concatenation_rejects_mismatched_formats():
    import io, wave
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    with pytest.raises(ValueError, match="formats differ"):
        revision_sections.concatenate_wavs([revision_wav(), buffer.getvalue()])


@pytest.mark.asyncio
async def test_structured_channel_marker_is_cleaned(monkeypatch):
    from app.services import modal_client
    answer = 'thought\n```json\n{"sections":[{"id":0,"title":"Topic","script":"A faithful revision."}]}\n```'
    monkeypatch.setattr(modal_client, "call_answer_generator", AsyncMock(return_value={"answer": answer}))
    sections = await revision_sections.generate_sections("A paragraph.")
    assert sections[0]["script"] == "A faithful revision."


def test_source_split_with_trailing_spaces_and_crlf():
    text = "First.  \r\n\r\nSecond. \r\n\r\nThird."
    sections = revision_sections.split_source(text)
    assert [s["source_text"] for s in sections] == ["First.", "Second.", "Third."]


@pytest.mark.asyncio
async def test_saved_section_audio_corruption_cannot_pass_verification(env, monkeypatch):
    doc, session, _, _, _ = section_fixture(env, monkeypatch)
    ticket = store.create("alice", session, doc, "audio_revision", revision_mode="sectioned")
    for tool in service.required_tools("audio_revision"):
        await service.execute_tool(tool, ticket)
    action = store.get(ticket)
    store.artifact(action["sections"][0]["audio_id"], "wav").write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        service.verify_section_manifest(action)


@pytest.mark.asyncio
@pytest.mark.parametrize("gateway_disconnect", [False, True])
async def test_gateway_background_tool_is_awaited_and_missing_tools_continue(env, monkeypatch, gateway_disconnect):
    import asyncio
    doc, session, _, _, tts = section_fixture(env, monkeypatch)
    settings = env[0]
    settings.actions_provider = "openclaw_mcp"
    ticket = store.create("alice", session, doc, "audio_revision", revision_mode="sectioned")
    calls = 0
    task = None
    async def gateway(action_id):
        nonlocal calls, task
        calls += 1
        if calls == 1:
            task = asyncio.create_task(service.execute_tool("summarize_document", action_id))
            await asyncio.sleep(0)
            if gateway_disconnect:
                import httpx
                raise httpx.ReadTimeout("Gateway disconnected")
        else:
            await service.execute_tool("create_revision_audio", action_id)
            await service.execute_tool("save_audio_revision", action_id)
    monkeypatch.setattr(service, "run_openclaw", gateway)
    await service.run_action(ticket)
    if task: await task
    action = store.get(ticket)
    assert action["status"] == "complete" and action["audio_saved"]
    assert calls == 2 and tts.await_count == 3
    assert action["trace"] == service.required_tools("audio_revision")


@pytest.mark.parametrize("text", [
    "\n".join(["This is a long wrapped source line containing facts for revision." * 2 for _ in range(8)]),
    " ".join(["This is one factual sentence from a long unbroken source paragraph." for _ in range(15)]),
])
def test_long_pdf_like_text_without_blank_paragraphs_has_three_exact_spans(text):
    sections = revision_sections.split_source(text)
    assert len(sections) == 3
    assert sections[0]["source_start"] == 0 and sections[-1]["source_end"] == len(text)
    for i, section in enumerate(sections):
        assert section["source_text"] == text[section["source_start"]:section["source_end"]]
        if i:
            assert not text[sections[i - 1]["source_end"]:section["source_start"]].strip()


def test_retry_audio_reuses_prepared_sections_and_rechecks_owner_source(env, monkeypatch):
    doc, session, app, generator, tts = section_fixture(env, monkeypatch)
    tts.side_effect = [(revision_wav(), 1), ValueError("Speech unavailable.")]
    with TestClient(app) as client:
        old = client.post("/api/v1/actions", json={"command": "Create an audio revision of this document",
            "document_id": doc, "session_id": session, "revision_mode": "sectioned"}).json()["action_id"]
        assert store.get(old)["status"] == "partial"
        app.dependency_overrides[get_current_user] = lambda: {"sub": "bob"}
        assert client.post(f"/api/v1/actions/{old}/retry").status_code == 404
        app.dependency_overrides[get_current_user] = lambda: {"sub": "alice"}
        tts.side_effect = None
        response = client.post(f"/api/v1/actions/{old}/retry")
        assert response.status_code == 202
        new = response.json()["action_id"]
        action = store.get(new)
        assert new != old and action["status"] == "complete" and action["audio_saved"]
        assert action["retry_of"] == old and store.get(old)["status"] == "partial"
        assert action["trace"] == service.required_tools("audio_revision")
        assert generator.await_count == 1 and tts.await_count == 4  # 2 first job, 2 missing sections.
        assert client.post(f"/api/v1/actions/{new}/retry").status_code == 409
        local_document_store.save_document(document_id=doc, user_id="alice", filename="lecture.txt",
            file_type="txt", chunk_count=1, uploaded_at=datetime.now(), content=b"Changed source.")
        assert client.post(f"/api/v1/actions/{old}/retry").status_code == 409


@pytest.mark.asyncio
async def test_tool_result_names_next_step_without_exposing_content(env, monkeypatch):
    doc, session, _, _, _ = section_fixture(env, monkeypatch)
    ticket = store.create("alice", session, doc, "audio_revision", revision_mode="sectioned")
    for tool, next_tool in [("summarize_document", "create_revision_audio"),
                            ("create_revision_audio", "save_audio_revision"), ("save_audio_revision", None)]:
        result = await service.execute_tool(tool, ticket)
        assert result["next_tool"] == next_tool
        assert result["workflow_complete"] == (next_tool is None)
        assert "script" not in result and "source_text" not in result
