"""Regression tests for the isolated Sinhala transcript -> existing RAG route."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


QUESTIONS = [
    "බල්ලන්ට විෂ සහිත ආහාර මොනවාද?",
    "බල්ලන්ගේ ජනප්‍රිය වර්ග මොනවාද?",
    "බල්ලෙකුට දිනපතා ව්‍යායාම අවශ්‍යද?",
    "චොකලට් බල්ලන්ට අනතුරුදායක ඇයි?",
]

CHUNK = {
    "text": "Chocolate contains theobromine, which is toxic to dogs.",
    "metadata": {
        "document_id": "06fa1d1b-a284-4e67-a2af-2710a6b8f74b",
        "filename": "dogs.pdf",
        "page": 3,
    },
    "score": 0.91,
    "retrieval_method": "dense",
}


@pytest.mark.parametrize("question", QUESTIONS)
def test_sinhala_questions_reuse_existing_pipeline_without_translation(question):
    client = TestClient(app)
    settings = SimpleNamespace(use_sinhala_rag_test=True)
    with (
        patch("app.api.v1.routes.test_sinhala_rag.get_settings", return_value=settings),
        patch("app.api.v1.routes.test_sinhala_rag.bge_m3_cache_status", return_value=(True, "ready")),
        patch("app.services.ingestion.hybrid_query_chunks", new_callable=AsyncMock, return_value=[CHUNK]) as retrieve,
        patch("app.api.v1.routes.test_sinhala_rag.call_rag_generator", new_callable=AsyncMock, return_value={"answer": "චොකලට් බල්ලන්ට විෂ සහිතය."}) as generate,
        patch("app.api.v1.routes.test_sinhala_rag.call_localizer", new_callable=AsyncMock, return_value={"localized_text": "චොකලට් බල්ලන්ට විෂ සහිතය."}) as localize,
    ):
        response = client.post("/api/v1/test/sinhala-rag", json={"transcript": question})

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == question
    assert body["retrieval_query"] == question
    assert body["language"] == "sinhala"
    assert body["translation_fallback_used"] is False
    assert body["answer"] == "චොකලට් බල්ලන්ට විෂ සහිතය."
    assert body["sources"][0]["filename"] == "dogs.pdf"
    assert body["sources"][0]["page"] == 3
    retrieve.assert_awaited_once_with(question, "guest", n_results=5)
    generate.assert_awaited_once_with(question, [CHUNK["text"]], "sinhala")
    localize.assert_awaited_once_with("චොකලට් බල්ලන්ට විෂ සහිතය.", "sinhala")


def test_sinhala_rag_route_is_disabled_by_default():
    client = TestClient(app)
    settings = SimpleNamespace(use_sinhala_rag_test=False)
    with patch("app.api.v1.routes.test_sinhala_rag.get_settings", return_value=settings):
        response = client.post("/api/v1/test/sinhala-rag", json={"transcript": QUESTIONS[0]})
    assert response.status_code == 503
