import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.llm_service import EmbeddingService, QwenModalService
from app.services.rag_service import RagService


class GenerationLatencyTests(unittest.TestCase):
    @patch("app.services.llm_service.httpx.post")
    @patch("app.services.llm_service.time.monotonic", return_value=100.0)
    def test_retries_share_one_deadline_even_with_long_endpoint_timeout(self, clock, post):
        response = Mock(status_code=200)
        response.json.return_value = {"response": "draft"}
        post.return_value = response
        service = QwenModalService(generation_budget_sec=15)
        with patch("app.services.llm_service.MODAL_REQUEST_TIMEOUT_SEC", 660):
            clock.return_value = 101.0
            service.call("first draft")
            self.assertEqual(post.call_args.kwargs["timeout"].read, 14)
            clock.return_value = 106.0
            service.call("repair draft")
            self.assertEqual(post.call_args.kwargs["timeout"].read, 9)
            clock.return_value = 116.0
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                service.call("another repair")
        self.assertEqual(post.call_count, 2)

    def test_concurrent_services_share_loaded_embedding_model(self):
        factory = Mock(return_value=Mock())
        module = SimpleNamespace(SentenceTransformer=factory)
        services = [EmbeddingService("test-model") for _ in range(8)]
        with patch.dict(sys.modules, {"sentence_transformers": module}):
            with patch.object(EmbeddingService, "_models", {}):
                with ThreadPoolExecutor(max_workers=8) as executor:
                    list(executor.map(lambda service: service._load(), services))
        factory.assert_called_once_with("test-model")
        self.assertTrue(all(service._model is services[0]._model for service in services))

    def test_session_merge_reuses_stored_vectors_and_keeps_document_alignment(self):
        service = RagService.__new__(RagService)
        service.client = Mock()
        service.embed = Mock()
        target = service.client.get_or_create_collection.return_value
        target.get.return_value = {"ids": ["a"]}
        service.client.get_collection.return_value.get.return_value = {
            "ids": ["a", "b"], "documents": ["first", "second"],
            "metadatas": [{"page": 1}, {"page": 2}],
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
        }
        self.assertEqual(service.merge_collections("session", ["doc"]), 1)
        service.embed.get_batch_embeddings.assert_not_called()
        target.add.assert_called_once_with(
            ids=["b"], documents=["second"], metadatas=[{"page": 2}],
            embeddings=[[0.3, 0.4]],
        )

    def test_session_merge_reencodes_when_vector_fetch_is_unsupported(self):
        service = RagService.__new__(RagService)
        service.client = Mock()
        service.embed = Mock()
        target = service.client.get_or_create_collection.return_value
        target.get.return_value = {"ids": []}
        service.client.get_collection.return_value.get.side_effect = [
            RuntimeError("old collection"),
            {"ids": ["a"], "documents": ["first"], "metadatas": [{"page": 1}]},
        ]
        service.embed.get_batch_embeddings.return_value = [[0.1, 0.2]]
        self.assertEqual(service.merge_collections("session", ["doc"]), 1)
        service.embed.get_batch_embeddings.assert_called_once_with(["first"])
        self.assertEqual(target.add.call_args.kwargs["embeddings"], [[0.1, 0.2]])
