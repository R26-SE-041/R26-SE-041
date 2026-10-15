from unittest import TestCase
import os
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from studio.main import app, require_user
from studio.pipeline import Pipeline, required_services
from studio.schemas import JobRequest
from studio.worker import process_job


class ConversationTests(TestCase):
    def setUp(self):
        self.owner = str(uuid4())
        self.generation = str(uuid4())

    def analysis(self):
        return {"id": "question.test", "mode": "ask", "question": "What does this part do?",
                "interaction": {"type": "point", "coords": [.4, .6]}}

    def test_recycle_bin_routes_preserve_assets_and_scope_operations_to_owner(self):
        app.dependency_overrides[require_user] = lambda: self.owner
        try:
            with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
                client = TestClient(app)
                repo.get_chat.return_value = {"id":"chat"}
                response = client.delete("/studio/chats/chat")
                self.assertEqual(response.json(),{"status":"trashed"})
                repo.set_chat_trashed.assert_called_once_with(self.owner,"chat",True)
                repo.delete_chat.assert_not_called()
                storage.assert_not_called()
                self.assertEqual(client.post("/studio/chats/chat/restore").status_code,200)
                repo.set_chat_trashed.assert_called_with(self.owner,"chat",False)
                self.assertEqual(client.delete("/studio/chats/chat/permanent").status_code,200)
                repo.delete_chat.assert_called_once_with(self.owner,"chat",storage.return_value.remove)
        finally:
            app.dependency_overrides.clear()

    def test_recycle_bin_listing_is_explicit_and_keeps_existing_pagination(self):
        app.dependency_overrides[require_user] = lambda: self.owner
        try:
            # Keep this unit test independent of local .env/Supabase credentials.
            with patch.dict(os.environ,{},clear=True), patch("studio.main.repo") as repo, \
                    patch("studio.main.Storage") as storage:
                repo.list_chats.return_value = []
                client = TestClient(app)
                self.assertEqual(client.get("/studio/chats").status_code,200)
                self.assertEqual(repo.list_chats.call_args.kwargs,{"trashed":False})
                self.assertEqual(client.get("/studio/chats?trashed=true&query=heart&before_id=older").status_code,200)
                self.assertEqual(repo.list_chats.call_args.kwargs,{"trashed":True})
                self.assertEqual(repo.list_chats.call_args.args[:4],(self.owner,None,"older","heart"))
                storage.return_value.signed_url.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_recycle_bin_missing_owner_and_active_jobs_fail_safely(self):
        app.dependency_overrides[require_user] = lambda: self.owner
        try:
            with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
                client = TestClient(app)
                repo.set_chat_trashed.side_effect = LookupError("missing")
                self.assertEqual(client.post("/studio/chats/foreign/restore").status_code,404)
                repo.get_chat.return_value = {"id":"chat"}
                repo.set_chat_trashed.side_effect = ValueError("Wait for active jobs")
                self.assertEqual(client.delete("/studio/chats/chat").status_code,409)
                storage.assert_not_called()
                repo.delete_chat.side_effect = ValueError("Move to Recycle Bin first")
                self.assertEqual(client.delete("/studio/chats/chat/permanent").status_code,409)
        finally:
            app.dependency_overrides.clear()

    def test_archive_signs_preview_and_validates_filters(self):
        app.dependency_overrides[require_user] = lambda: self.owner
        try:
            with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
                repo.list_chats.return_value = [{"id": "chat", "preview_path": self.owner+"/thumb.png", "version_count": 2}]
                storage.return_value.signed_url.return_value = "https://storage.example/signed"
                client = TestClient(app)
                response = client.get("/studio/chats?mode=anatomy&query=heart&since=2026-10-01T00:00:00Z")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()[0]["imageUrl"], "https://storage.example/signed")
                self.assertNotIn("preview_path", response.json()[0])
                self.assertEqual(repo.list_chats.call_args.args[0], self.owner)
                self.assertEqual(repo.list_chats.call_args.args[3:5], ("heart", "anatomy"))
                repo.list_chats.reset_mock()
                self.assertEqual(client.get("/studio/chats?mode=unknown").status_code, 422)
                self.assertEqual(client.get("/studio/chats?since=invalid").status_code, 422)
                repo.list_chats.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_question_requires_a_source_image_and_valid_coordinates(self):
        with self.assertRaises(ValueError):
            JobRequest(request_id=uuid4(), kind="analysis", analysis=self.analysis())
        for coords in ([float("nan"), .5], [1.2, .5], [.5, .5, .5]):
            with self.subTest(coords=coords), self.assertRaises(ValueError):
                JobRequest(request_id=uuid4(), kind="analysis", generation_id=self.generation,
                           analysis={**self.analysis(), "interaction": {"type": "point", "coords": coords}})
        self.assertEqual(required_services({"kind": "analysis"}), {"interactive"})

    def test_answer_is_saved_by_worker_before_job_reports_completion(self):
        repo, storage = Mock(), Mock()
        repo.get_history.return_value = {"id": self.generation, "image_path": "owner/image.png",
                                         "metadata": {"chatId": "chat.test"}}
        repo.heartbeat.return_value = True
        storage.download.return_value = "saved-source-image"
        pipeline = Pipeline(repo=repo, storage=storage)
        pipeline.invoke = Mock(return_value={"response_text": "The selected part transports nutrients."})
        job = {"id": str(uuid4()), "user_id": self.owner, "kind": "analysis", "state": {},
               "payload": {"generation_id": self.generation, "speed_mode": "pro", "analysis": self.analysis()}}
        result = pipeline.process_source(job)
        self.assertEqual(result["interaction_id"], "question.test")
        saved = repo.append_interaction.call_args.args[2]
        self.assertEqual(saved["selection"]["coords"], [.4, .6])
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(pipeline.invoke.call_args.args[3]["image_base64"], "saved-source-image")

    def test_failed_question_remains_in_history_with_its_selection(self):
        repo, pipeline = Mock(), Mock()
        pipeline.run.side_effect = RuntimeError("Model unavailable")
        job = {"id": str(uuid4()), "user_id": self.owner, "generation_id": self.generation,
               "kind": "analysis", "payload": {"analysis": self.analysis()}}
        process_job(repo, pipeline, job)
        saved = repo.append_interaction.call_args.args[2]
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["error"], "Model unavailable")
        self.assertEqual(saved["selection"]["coords"], [.4, .6])

    def test_other_owner_cannot_read_conversation_events(self):
        app.dependency_overrides[require_user] = lambda: self.owner
        try:
            with patch("studio.main.repo") as repo:
                repo.get_chat.return_value = None
                response = TestClient(app).get("/studio/chats/private-chat/events")
                self.assertEqual(response.status_code, 404)
                repo.get_chat.assert_called_once_with(self.owner, "private-chat")
                repo.list_chat_events.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_blank_conversation_title_is_rejected(self):
        app.dependency_overrides[require_user] = lambda: self.owner
        try:
            with patch("studio.main.repo") as repo:
                response = TestClient(app).patch("/studio/chats/chat.test", json={"title": "   "})
                self.assertEqual(response.status_code, 422)
                repo.rename_chat.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_enhancement_saves_original_and_full_payload_before_completion(self):
        repo, storage = Mock(), Mock()
        repo.heartbeat.return_value = True
        pipeline = Pipeline(repo=repo, storage=storage)
        enhanced = {"final_prompt": "White background, detailed botanical drawing", "generic_spec": {"subject": "leaf"}}
        pipeline.invoke = Mock(return_value={"enhanced_prompt_json": enhanced})
        job = {"id": str(uuid4()), "user_id": self.owner, "kind": "enhance", "state": {},
               "payload": {"prompt": "draw leaf", "raw_prompt": "leaf", "mode": "general",
                           "chat_id": "chat.test", "speed_mode": "normal", "enhancement_context": {}}}
        result = pipeline.run(job)
        data = repo.append_chat_event.call_args.args[4]
        self.assertEqual(data["originalPrompt"], "leaf")
        self.assertEqual(data["payload"], enhanced)
        self.assertEqual(data["speedMode"], "normal")
        self.assertEqual(result["chat_id"], "chat.test")
        repo.heartbeat.return_value = False
        repo.append_chat_event.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "lease"):
            pipeline.run(job)
        repo.append_chat_event.assert_not_called()
