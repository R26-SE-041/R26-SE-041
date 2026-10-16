import base64
import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core import auth
from app.core.auth import AuthUser, require_user
from app.core.config import settings
from app.api import accounts
from app.services import persistence
from main import app

USER = AuthUser("11111111-1111-4111-8111-111111111111", "one@example.com", "One", "verified-user-token")
OTHER_RUN = "22222222-2222-4222-8222-222222222222"


class AccountSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def configured(self):
        return patch.multiple(settings, storage_backend="supabase", supabase_url="https://example.supabase.co", supabase_publishable_key=SecretStr("public-key"))

    def test_supabase_processing_requires_login_before_inference(self):
        with self.configured(), patch("app.api.routes.srcnn_client.enhance_image", AsyncMock()) as model:
            response = self.client.post("/api/process", files={"file": ("test.png", b"image", "image/png")})
        self.assertEqual(response.status_code, 401)
        model.assert_not_called()

    def test_forged_bearer_token_is_rejected_by_supabase_auth(self):
        upstream = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(lambda r: httpx.Response(401)))
        with self.configured(), patch.object(auth, "user_client", return_value=upstream):
            response = self.client.get("/api/history", headers={"Authorization": "Bearer forged-jwt"})
        self.assertEqual(response.status_code, 401)

    def test_auth_network_failure_does_not_grant_access(self):
        def fail(request):
            raise httpx.ConnectError("private upstream", request=request)
        upstream = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(fail))
        with self.configured(), patch.object(auth, "user_client", return_value=upstream):
            response = self.client.get("/api/history", headers={"Authorization": "Bearer token"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private upstream", response.text)

    def test_history_filters_by_verified_user_and_uses_user_token(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json=[{"id": OTHER_RUN, "filename": "notes.png"}])
        upstream = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        app.dependency_overrides[require_user] = lambda: USER
        with patch.object(accounts, "user_client", return_value=upstream) as factory:
            response = self.client.get("/api/history?user_id=attacker&limit=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(requests[0].url.params["user_id"], "eq." + USER.id)
        factory.assert_called_once_with(USER.access_token)

    def test_other_users_history_item_is_not_found(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json=[])
        app.dependency_overrides[require_user] = lambda: USER
        upstream = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        with patch.object(accounts, "user_client", return_value=upstream):
            response = self.client.get("/api/history/" + OTHER_RUN)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(requests[0].url.params["user_id"], "eq." + USER.id)

    def test_delete_cannot_target_another_user(self):
        app.dependency_overrides[require_user] = lambda: USER
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json=[])
        upstream = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        with patch.object(accounts, "user_client", return_value=upstream):
            response = self.client.delete("/api/history/" + OTHER_RUN)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(requests[0].method, "GET")
        self.assertEqual(requests[0].url.params["user_id"], "eq." + USER.id)

    def test_signin_does_not_return_password_or_internal_auth_fields(self):
        payload = {"access_token": "user-access", "refresh_token": "user-refresh", "expires_in": 3600,
                   "user": {"id": USER.id, "email": USER.email, "user_metadata": {"display_name": "One"}, "app_metadata": {"internal": True}}}
        with patch.object(accounts, "auth_request", AsyncMock(return_value=payload)), patch.object(accounts, "record_auth_event", AsyncMock()) as event:
            response = self.client.post("/api/auth/signin", json={"email": USER.email, "password": "test-password"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("test-password", response.text)
        self.assertNotIn("app_metadata", response.text)
        event.assert_awaited_once_with(USER.id, "sign_in")

    def test_history_detail_returns_images_and_all_languages(self):
        app.dependency_overrides[require_user] = lambda: USER
        row = {"id": OTHER_RUN, "extracted_text": "Sinhala", "extracted_text_ta": "Tamil", "extracted_text_en": "English",
               "original_image_path": f"{USER.id}/{OTHER_RUN}/original", "enhanced_image_path": f"{USER.id}/{OTHER_RUN}/enhanced"}
        urls = {"original_image_url": "https://storage.test/original", "enhanced_image_url": "https://storage.test/enhanced"}
        with patch.object(accounts, "history_request", AsyncMock(return_value=[row])), patch.object(accounts, "history_image_urls", AsyncMock(return_value=urls)):
            response = self.client.get("/api/history/" + OTHER_RUN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["enhanced_image_url"], urls["enhanced_image_url"])
        self.assertEqual(response.json()["extracted_text_ta"], "Tamil")
        self.assertNotIn("original_image_path", response.json())

    def test_storage_outage_keeps_saved_text_readable(self):
        app.dependency_overrides[require_user] = lambda: USER
        with patch.object(accounts, "history_request", AsyncMock(return_value=[{"id": OTHER_RUN, "extracted_text": "notes"}])), patch.object(accounts, "history_image_urls", AsyncMock(side_effect=persistence.PersistenceError("private internal error"))):
            response = self.client.get("/api/history/" + OTHER_RUN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["extracted_text"], "notes")
        self.assertIn("image_error", response.json())
        self.assertNotIn("private internal error", response.text)

    def test_delete_checks_ownership_before_deleting_storage(self):
        app.dependency_overrides[require_user] = lambda: USER
        with patch.object(accounts, "history_request", AsyncMock(return_value=[])), patch.object(accounts, "remove_run_images", AsyncMock()) as cleanup:
            response = self.client.delete("/api/history/" + OTHER_RUN)
        self.assertEqual(response.status_code, 404)
        cleanup.assert_not_awaited()

    def test_delete_removes_images_and_owned_row(self):
        app.dependency_overrides[require_user] = lambda: USER
        with patch.object(accounts, "history_request", AsyncMock(side_effect=[[{"id": OTHER_RUN}], [{"id": OTHER_RUN}]])) as db, patch.object(accounts, "remove_run_images", AsyncMock()) as cleanup:
            response = self.client.delete("/api/history/" + OTHER_RUN)
        self.assertEqual(response.status_code, 200)
        cleanup.assert_awaited_once_with(USER.id, OTHER_RUN)
        self.assertEqual(db.await_args_list[1].args[1], "DELETE")

    def test_failed_image_deletion_retains_history_for_retry(self):
        app.dependency_overrides[require_user] = lambda: USER
        with patch.object(accounts, "history_request", AsyncMock(return_value=[{"id": OTHER_RUN}])) as db, patch.object(accounts, "remove_run_images", AsyncMock(side_effect=persistence.PersistenceError("internal"))):
            response = self.client.delete("/api/history/" + OTHER_RUN)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(db.await_count, 1)


class HistoryPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_entry_needs_no_storage_request(self):
        with patch.object(persistence, "supabase_client") as storage:
            urls = await persistence.history_image_urls({"id": OTHER_RUN}, USER)
        self.assertEqual(urls, {})
        storage.assert_not_called()

    async def test_other_owners_image_paths_cannot_be_signed(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"signedURL": "/object/sign/ocr-history/own?token=short-lived"})
        upstream = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        row = {"id": OTHER_RUN, "original_image_path": f"attacker/{OTHER_RUN}/original",
               "enhanced_image_path": f"{USER.id}/{OTHER_RUN}/enhanced"}
        with patch.object(settings, "supabase_url", "https://example.supabase.co"), patch.object(persistence, "supabase_client", return_value=upstream):
            urls = await persistence.history_image_urls(row, USER)
        self.assertEqual(len(requests), 1)
        self.assertIn(f"/{USER.id}/{OTHER_RUN}/enhanced", requests[0].url.path)
        self.assertNotIn("original_image_url", urls)
        self.assertEqual(urls["enhanced_image_url"], "https://example.supabase.co/storage/v1/object/sign/ocr-history/own?token=short-lived")

    async def test_owner_is_bound_to_verified_user_and_image_bytes_are_excluded_from_row(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(201)
        upstream = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(respond))
        storage = httpx.AsyncClient(base_url="https://example.supabase.co", transport=httpx.MockTransport(lambda r: httpx.Response(201)))
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nprivate").decode()
        result = {"extracted_text": "notes", "user_id": "attacker", "original_b64": image, "enhanced_b64": image, "lines": [{"crop_b64": "private", "confidence": .9}]}
        with patch.object(settings, "storage_backend", "supabase"), patch.object(persistence, "user_client", return_value=upstream), patch.object(persistence, "supabase_client", return_value=storage):
            await persistence.save_run(result, USER, "notes.png")
        body = json.loads(requests[0].content)
        self.assertEqual(body["user_id"], USER.id)
        self.assertNotIn("private", requests[0].content.decode())

    async def test_supabase_never_saves_an_unowned_run(self):
        with patch.object(settings, "storage_backend", "supabase"):
            with self.assertRaises(persistence.PersistenceError):
                await persistence.save_run({"extracted_text": "notes"})
