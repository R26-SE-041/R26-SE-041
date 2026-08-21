"""Latency-safe behavior tests for transcript-to-answer retrieval."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import ingestion


class _Collection:
    async def count(self):
        await asyncio.sleep(0.03)
        return 2

    async def query(self, **_kwargs):
        await asyncio.sleep(0.12)
        return {
            "documents": [["BGE-M3 dense retrieval", "BM25 sparse retrieval"]],
            "metadatas": [[{"filename": "architecture.txt"}] * 2],
            "distances": [[0.1, 0.2]],
        }


@pytest.mark.asyncio
async def test_dense_and_bm25_overlap_without_changing_reranked_sources():
    """The two independent ranked lists must overlap in time and still reach reranking."""

    async def embed(_texts):
        await asyncio.sleep(0.08)
        return [[0.0] * 1024]

    async def warm_bm25(_user_id):
        await asyncio.sleep(0.15)

    sparse = [
        {
            "text": "BM25 sparse retrieval",
            "metadata": {"filename": "architecture.txt"},
            "bm25_score": 4.0,
        }
    ]

    async def rerank(_query, candidates, top_k):
        assert {item["text"] for item in candidates} == {
            "BGE-M3 dense retrieval",
            "BM25 sparse retrieval",
        }
        return candidates[:top_k]

    with (
        patch.object(ingestion, "get_settings", return_value=SimpleNamespace(use_modal_retrieval_models=True)),
        patch.object(ingestion, "get_or_create_collection", new=AsyncMock(return_value=_Collection())),
        patch.object(ingestion, "_ensure_bm25_loaded", side_effect=warm_bm25),
        patch.object(ingestion._bm25_store, "search", return_value=sparse),
        patch("app.services.modal_client.call_bge_embed", side_effect=embed),
        patch("app.services.modal_client.call_bge_rerank", side_effect=rerank),
    ):
        started = time.perf_counter()
        result = await ingestion.hybrid_query_chunks(
            "What are the retrieval stages?", "guest", n_results=2
        )
        elapsed = time.perf_counter() - started

    # Dense is ~0.23 s and sparse is ~0.15 s. Sequential execution is ~0.38 s;
    # parallel execution should stay close to the slower dense branch.
    assert elapsed < 0.32
    assert {item["text"] for item in result} == {
        "BGE-M3 dense retrieval",
        "BM25 sparse retrieval",
    }

