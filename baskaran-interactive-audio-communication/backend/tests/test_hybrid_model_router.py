from app.services.model_router import (
    DOCUMENT_RAG_BASE,
    GENERAL_BASE,
    MUSCLE_FINETUNED_V2,
    choose_answer_route,
)
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.v1.routes.documents import ask_question
from app.schemas.document import AskRequest


def _route(question, *, document_grounded=False, memento=None):
    return choose_answer_route(question, document_grounded=document_grounded, memento=memento).name


def test_english_and_tamil_five_muscle_questions_use_v2():
    assert _route("What are the functions of biceps brachii?") == MUSCLE_FINETUNED_V2
    assert _route("Deltoid muscle-க்கு nerve supply என்ன?") == MUSCLE_FINETUNED_V2


def test_sinhala_five_muscle_question_uses_v2():
    assert _route("Quadriceps femoris එකේ main function මොකක්ද?") == MUSCLE_FINETUNED_V2


def test_document_route_wins_over_five_muscle_match():
    assert _route("According to this document, explain biceps brachii.", document_grounded=True) == DOCUMENT_RAG_BASE
    assert _route("What does this document say about dependency injection?", document_grounded=True) == DOCUMENT_RAG_BASE


def test_safe_muscle_follow_up_and_document_precedence():
    memento = {"previous_question": "Explain the biceps brachii."}
    assert _route("Which nerve supplies it?", memento=memento) == MUSCLE_FINETUNED_V2
    assert _route("Which nerve supplies it?", document_grounded=True, memento=memento) == DOCUMENT_RAG_BASE


def test_new_topic_cannot_inherit_muscle_route():
    memento = {"previous_question": "Explain the biceps brachii."}
    assert _route("New topic: Explain RAM and ROM.", memento=memento) == GENERAL_BASE


def test_general_question_uses_base_without_rag():
    assert _route("What is dependency injection?") == GENERAL_BASE


def test_non_document_request_mocks_only_the_selected_model_call():
    with (
        patch("app.api.v1.routes.documents.get_settings", return_value=SimpleNamespace(debug=True)),
        patch("app.api.v1.routes.documents.call_answer_generator", new_callable=AsyncMock, return_value={"answer": "ok"}) as generate,
        patch("app.services.ingestion.hybrid_query_chunks", new_callable=AsyncMock) as retrieve,
    ):
        response = asyncio.run(ask_question(
            AskRequest(transcript="What are the functions of biceps brachii?"),
            current_user={"sub": "test-user"},
        ))
    assert response.route == MUSCLE_FINETUNED_V2
    generate.assert_awaited_once()
    assert generate.await_args.kwargs["route"] == MUSCLE_FINETUNED_V2
    retrieve.assert_not_awaited()
