"""Language routing tests for the temporary direct-Gemma experiment."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.routes.documents import ask_question
from app.schemas.document import AskRequest


CHUNKS = [
    {
        "text": "Newton's second law states that force equals mass times acceleration.",
        "metadata": {
            "document_id": str(uuid.uuid4()),
            "filename": "physics-notes.pdf",
            "page": 4,
        },
        "score": 0.91,
    }
]


def _ask(language: str, direct: bool):
    generated = f"grounded-{language}"
    with (
        patch(
            "app.api.v1.routes.documents.bge_m3_cache_status",
            return_value=(True, "ready"),
        ),
        patch(
            "app.api.v1.routes.documents.get_settings",
            return_value=SimpleNamespace(use_direct_multilingual_gemma=direct),
        ),
        patch(
            "app.services.ingestion.hybrid_query_chunks",
            new_callable=AsyncMock,
            return_value=CHUNKS,
        ) as retrieve,
        patch(
            "app.api.v1.routes.documents.call_answer_generator",
            new_callable=AsyncMock,
            return_value={"answer": generated},
        ) as gemma,
        patch(
            "app.api.v1.routes.documents.call_localizer",
            new_callable=AsyncMock,
            return_value={"localized_text": f"localized-{language}"},
        ) as localizer,
    ):
        response = asyncio.run(
            ask_question(
                AskRequest(transcript="What is Newton's second law?", language=language, document_grounded=True),
                current_user={"sub": "test-user"},
            )
        )
    return response, retrieve, gemma, localizer


@pytest.mark.parametrize("language", ["english", "tamil", "sinhala"])
def test_direct_mode_passes_selected_language_to_gemma_and_bypasses_localizer(language):
    response, retrieve, gemma, localizer = _ask(language, direct=True)

    retrieve.assert_awaited_once_with(
        "What is Newton's second law?", "test-user", n_results=5
    )
    gemma.assert_awaited_once()
    assert gemma.await_args.args == ("What is Newton's second law?", language)
    assert gemma.await_args.kwargs["route"] == "document_rag_base"
    assert gemma.await_args.kwargs["context_chunks"] == [CHUNKS[0]["text"]]
    localizer.assert_not_awaited()
    assert response.answer == f"grounded-{language}"
    assert response.references[0].filename == "physics-notes.pdf"


@pytest.mark.parametrize("language", ["tamil", "sinhala"])
def test_disabled_flag_restores_legacy_english_then_localizer(language):
    response, _, gemma, localizer = _ask(language, direct=False)

    gemma.assert_awaited_once()
    assert gemma.await_args.args == ("What is Newton's second law?", "english")
    assert gemma.await_args.kwargs["route"] == "document_rag_base"
    assert gemma.await_args.kwargs["context_chunks"] == [CHUNKS[0]["text"]]
    localizer.assert_awaited_once_with(f"grounded-{language}", language)
    assert response.answer == f"localized-{language}"


def test_english_is_unchanged_when_flag_is_disabled():
    response, _, gemma, localizer = _ask("english", direct=False)

    gemma.assert_awaited_once()
    assert gemma.await_args.args == ("What is Newton's second law?", "english")
    assert gemma.await_args.kwargs["route"] == "document_rag_base"
    assert gemma.await_args.kwargs["context_chunks"] == [CHUNKS[0]["text"]]
    localizer.assert_not_awaited()
    assert response.answer == "grounded-english"
