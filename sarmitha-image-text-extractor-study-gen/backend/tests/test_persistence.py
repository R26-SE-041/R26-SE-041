import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.auth import AuthUser
from app.services import persistence
from main import app

USER = AuthUser("11111111-1111-4111-8111-111111111111", "test@example.com", "Test", "test-token")


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_stores_private_images_and_only_paths_in_database(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(201)

        def client(*args):
            return httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nprivate-page").decode()
        with patch.object(settings, "storage_backend", "supabase"), patch.object(persistence, "user_client", side_effect=client), patch.object(persistence, "supabase_client", side_effect=client):
            result = await persistence.save_run({
                "extracted_text": "Sinhala text", "original_b64": image,
                "enhanced_b64": image, "extracted_text_ta": "Tamil", "extracted_text_en": "English",
                "lines": [{"crop_b64": "private-crop", "confidence": 0.9}],
            }, USER, "notes.png")
        self.assertIsNotNone(result)
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[0].headers["content-type"], "image/png")
        self.assertIn(f"/{USER.id}/{result}/original", requests[0].url.path)
        self.assertIn(f"/{USER.id}/{result}/enhanced", requests[1].url.path)
        body = requests[2].content
        self.assertNotIn(b"private", body)
        self.assertIn(b"confidence", body)
        row = json.loads(body)
        self.assertEqual(row["original_image_path"], f"{USER.id}/{result}/original")
        self.assertEqual(row["extracted_text_ta"], "Tamil")
        self.assertEqual(row["extracted_text_en"], "English")

    async def test_run_cleans_up_both_images_when_database_insert_fails(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(500 if request.url.path == "/rest/v1/ocr_runs" else 200)
        def client(*args):
            return httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        image = base64.b64encode(b"\xff\xd8\xffprivate-image").decode()
        with patch.object(settings, "storage_backend", "supabase"), patch.object(persistence, "user_client", side_effect=client), patch.object(persistence, "supabase_client", side_effect=client):
            with self.assertRaises(persistence.PersistenceError):
                await persistence.save_run({"extracted_text": "notes", "original_b64": image, "enhanced_b64": image}, USER)
        self.assertEqual([r.method for r in requests], ["POST", "POST", "POST", "DELETE"])
        self.assertEqual(len(json.loads(requests[-1].content)["prefixes"]), 2)

    async def test_failed_second_upload_cleans_up_without_saving_incomplete_history(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(500 if request.url.path.endswith("/enhanced") else 200)
        def client(*args):
            return httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nimage").decode()
        with patch.object(settings, "storage_backend", "supabase"), patch.object(persistence, "user_client", side_effect=client), patch.object(persistence, "supabase_client", side_effect=client):
            with self.assertRaises(persistence.PersistenceError):
                await persistence.save_run({"extracted_text": "notes", "original_b64": image, "enhanced_b64": image}, USER)
        self.assertEqual([r.method for r in requests], ["POST", "POST", "DELETE"])

    async def test_feedback_rolls_back_uploaded_object_if_insert_fails(self):
        calls = []

        def respond(request):
            calls.append((request.method, request.url.path))
            return httpx.Response(500 if request.url.path == "/rest/v1/ocr_feedback" else 200)

        client = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        with patch.object(settings, "storage_backend", "supabase"), patch.object(persistence, "supabase_client", return_value=client):
            with self.assertRaises(persistence.PersistenceError):
                await persistence.save_feedback(b"jpeg", "correction", USER)
        self.assertEqual([method for method, _ in calls], ["POST", "POST", "DELETE"])
        self.assertEqual(calls[-1][1], "/storage/v1/object/ocr-feedback")

    async def test_local_feedback_keeps_training_dataset_format(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(settings, "storage_backend", "local"), patch.object(persistence, "DATASET_DIR", Path(directory)):
                feedback_id = await persistence.save_feedback(b"image", "correct text")
            row = json.loads((Path(directory) / "metadata.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(row["text"], "correct text")
            self.assertEqual(row["file_name"], f"images/{feedback_id}.jpg")
            self.assertEqual((Path(directory) / row["file_name"]).read_bytes(), b"image")


class StorageRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_rejects_invalid_and_oversized_base64(self):
        save = AsyncMock()
        with patch("app.api.feedback.save_feedback", save):
            response = self.client.post("/api/feedback/ocr", json={"crop_b64": "invalid!", "corrected_text": "text"})
            self.assertEqual(response.status_code, 400)
            with patch.object(settings, "max_upload_bytes", 2):
                response = self.client.post("/api/feedback/ocr", json={"crop_b64": base64.b64encode(b"123").decode(), "corrected_text": "text"})
                self.assertEqual(response.status_code, 413)
        save.assert_not_called()

    def test_storage_failure_returns_unavailable_without_internal_details(self):
        with patch("app.api.feedback.save_feedback", AsyncMock(side_effect=persistence.PersistenceError("secret-token"))):
            response = self.client.post("/api/feedback/ocr", json={"crop_b64": "aW1hZ2U=", "corrected_text": "text"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret-token", response.text)

    def test_readiness_fails_if_supabase_is_down(self):
        with patch.object(settings, "storage_backend", "supabase"), patch.object(settings, "srcnn_modal_url", "https://model.test"), patch.object(settings, "trocr_modal_url", "https://model.test"), patch("app.api.routes.check_database", AsyncMock(side_effect=RuntimeError("secret"))):
            response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)
