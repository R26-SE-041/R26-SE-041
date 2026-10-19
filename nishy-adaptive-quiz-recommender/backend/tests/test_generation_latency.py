import sys
import os
from collections import OrderedDict
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.llm_service import EmbeddingService, QwenModalService
from app.services.rag_service import RagService
from app.agents.quiz_agent import _session_source_chunks
from modal_inference.json_stopping import complete_json_object


class EmbeddingStartupTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.graph.graph.get_graph")
    @patch("app.services.llm_service.EmbeddingService")
    async def test_server_warms_local_model_before_serving(self, embedding, graph):
        from app.main import lifespan
        with patch.dict(os.environ, {"PRELOAD_EMBEDDINGS": "true"}):
            async with lifespan(Mock()):
                embedding.return_value.get_embedding.assert_called_once()
                graph.assert_called_once()

    @patch("app.graph.graph.get_graph")
    @patch("app.services.llm_service.EmbeddingService")
    async def test_lazy_loading_can_be_explicitly_selected(self, embedding, graph):
        from app.main import lifespan
        with patch.dict(os.environ, {"PRELOAD_EMBEDDINGS": "false"}):
            async with lifespan(Mock()):
                embedding.assert_not_called()


class GenerationLatencyTests(unittest.TestCase):
    def setUp(self):
        self.status_patch = patch.object(QwenModalService, "_endpoint_status", {})
        self.status_patch.start()
        self.addCleanup(self.status_patch.stop)

    @patch("app.services.llm_service.httpx.get")
    @patch("app.services.llm_service.time.monotonic", return_value=100.0)
    def test_health_probe_is_reused_across_question_services_and_expires(self, clock, get):
        get.return_value.json.return_value = {"status": "ok"}
        with patch("app.services.llm_service.MODAL_HEALTH_CACHE_SEC", 30):
            self.assertTrue(QwenModalService().check_health())
            clock.return_value = 129
            self.assertTrue(QwenModalService().check_health())
            self.assertEqual(get.call_count, 1)
            clock.return_value = 131
            self.assertTrue(QwenModalService().check_health())
            self.assertEqual(get.call_count, 2)

    @patch("app.services.llm_service.httpx.get")
    @patch("app.services.llm_service.httpx.post")
    @patch("app.services.llm_service.time.monotonic", return_value=100.0)
    def test_inference_timeout_overrides_positive_health_then_recovers(self, clock, post, get):
        import httpx
        get.return_value.json.return_value = {"status": "ok"}
        post.side_effect = httpx.ReadTimeout("cold GPU")
        with patch("app.services.llm_service.MODAL_FAILURE_COOLDOWN_SEC", 30):
            self.assertTrue(QwenModalService().check_health())
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                QwenModalService().call("question")
            self.assertFalse(QwenModalService().check_health())
            get.assert_called_once()
            clock.return_value = 131
            self.assertTrue(QwenModalService().check_health())
            self.assertEqual(get.call_count, 2)

    def test_embedding_cache_reuses_sources_preserves_order_and_returns_copies(self):
        import numpy as np
        first, second = EmbeddingService("cache-test"), EmbeddingService("cache-test")
        model = Mock()
        model.encode.side_effect = [np.array([[1., 0.], [0., 1.]]), np.array([[.5, .5]])]
        first._model = second._model = model
        with patch.object(EmbeddingService, "_vectors", OrderedDict()):
            vectors = first.get_batch_embeddings(["source", "question", "source"])
            vectors[0][0] = 99
            self.assertEqual(second.get_embedding("source"), [1., 0.])
            self.assertEqual(second.get_batch_embeddings(["new question", "source"]), [[.5, .5], [1., 0.]])
        self.assertEqual(model.encode.call_count, 2)
        self.assertEqual(model.encode.call_args_list[0].args[0], ["source", "question"])
        self.assertEqual(model.encode.call_args_list[1].args[0], ["new question"])

    def test_embedding_cache_is_bounded_and_separates_models(self):
        import numpy as np
        first, second = EmbeddingService("model-a"), EmbeddingService("model-b")
        first._model = Mock()
        first._model.encode.return_value = np.array([[1., 0.]])
        second._model = Mock()
        second._model.encode.return_value = np.array([[0., 1.]])
        with patch.object(EmbeddingService, "_vectors", OrderedDict()) as cache:
            with patch("app.services.llm_service.EMBEDDING_CACHE_SIZE", 1):
                self.assertEqual(first.get_embedding("source"), [1., 0.])
                self.assertEqual(second.get_embedding("source"), [0., 1.])
                self.assertEqual(len(cache), 1)
                first.get_embedding("source")
                self.assertEqual(first._model.encode.call_count, 2)

    def test_session_source_snapshot_avoids_chroma_reads(self):
        rag = Mock()
        chunks = [{"text": "one"}, {"text": "two"}]
        self.assertEqual(_session_source_chunks({"raw_chunks": chunks}, rag, 1), chunks[:1])
        rag.get_source_chunks.assert_not_called()

    def test_old_checkpoint_without_source_snapshot_still_reads_chroma(self):
        rag = Mock()
        self.assertIs(_session_source_chunks({"chroma_collection_id": "s1"}, rag, 200), rag.get_source_chunks.return_value)
        rag.get_source_chunks.assert_called_once_with("s1", limit=200)

    def test_json_stopping_waits_for_outer_object_and_ignores_braces_in_strings(self):
        self.assertFalse(complete_json_object('{"questions":[{"options":{"1":"value"}}'))
        self.assertFalse(complete_json_object('{"question":"unfinished'))
        self.assertFalse(complete_json_object("plain prose"))
        self.assertTrue(complete_json_object('```json\n{"question":"A } and { in a string", "options":{"1":"answer"}}\n```'))
        self.assertTrue(complete_json_object('{"insufficient_context":true} trailing text'))

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
