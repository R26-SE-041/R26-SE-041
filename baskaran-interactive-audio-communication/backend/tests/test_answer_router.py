"""No topic or old session state can select a retired specialized model."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from app.services.model_router import DOCUMENT_RAG_BASE, GENERAL_BASE, choose_answer_route
from app.services.modal_client import call_answer_generator
from app.schemas.document import AskRequest
from app.api.v1.routes.documents import ask_question

@pytest.mark.parametrize("question", ["Explain biceps brachii.", "Explain dependency injection.", "Which nerve supplies it?"])
def test_topics_and_old_memory_use_only_supported_routes(question):
    memory = {"previous_question": "Explain biceps brachii."}
    assert choose_answer_route(question, document_grounded=True, memento=memory).name == DOCUMENT_RAG_BASE
    assert choose_answer_route(question, document_grounded=False, memento=memory).name == GENERAL_BASE


def test_default_request_uses_documents():
    assert AskRequest(transcript="Explain my notes.").document_grounded is True


def test_non_document_base_request_preserves_general_answers_without_retrieval():
    with (
        patch("app.api.v1.routes.documents.get_settings", return_value=SimpleNamespace(debug=True)),
        patch("app.api.v1.routes.documents.call_answer_generator", new_callable=AsyncMock, return_value={"answer": "ok"}) as generate,
        patch("app.services.ingestion.hybrid_query_chunks", new_callable=AsyncMock) as retrieve,
    ):
        result=asyncio.run(ask_question(AskRequest(transcript="Explain biceps brachii.", document_grounded=False), current_user={"sub":"test"}))
    assert result.route == GENERAL_BASE
    assert generate.await_args.kwargs["route"] == GENERAL_BASE
    retrieve.assert_not_awaited()


def test_retired_route_is_rejected_before_any_http_call():
    with patch("app.services.modal_client._http.post", new_callable=AsyncMock) as post:
        with pytest.raises(ValueError, match="Unsupported answer route"):
            asyncio.run(call_answer_generator("Question", "english", route="retired_specialized_route"))
        post.assert_not_awaited()
