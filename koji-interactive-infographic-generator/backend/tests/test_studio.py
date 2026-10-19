from __future__ import annotations
import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4
from fastapi.testclient import TestClient
from studio.main import app, require_user
from studio.schemas import JobRequest, Annotation
from studio.pipeline import Pipeline, configured_endpoints, required_services, evaluation_result
from studio.worker import process_job

USER_A = str(uuid4())
USER_B = str(uuid4())

class ReadinessTests(unittest.TestCase):
    def test_missing_recycle_bin_migration_blocks_release_readiness(self):
        self.check_schema(recycle_bin=False, expected_status=503)

    def test_migrated_schema_is_ready(self):
        self.check_schema(recycle_bin=True, expected_status=200)

    def check_schema(self, *, recycle_bin, expected_status):
        from unittest.mock import MagicMock
        connection = MagicMock()
        cursor = connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(False,), (recycle_bin,)]
        settings = {key: "configured" for key in (
            "DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")}
        with patch.dict(os.environ, settings, clear=True), patch("studio.repository.connection", connection):
            response = TestClient(app).get("/ready")
        self.assertEqual(response.status_code, expected_status)
        if expected_status == 503:
            self.assertIn("006_recycle_bin.sql", response.json()["detail"])

class JobContractTests(unittest.TestCase):
    def test_blank_erased_sketch_is_not_queued(self):
        with self.assertRaisesRegex(ValueError,"blank"):
            JobRequest(request_id=uuid4(),kind="sketch",sketch={"strokes":[
                {"points":[[.5,.5]],"width":.01},{"points":[[.5,.5]],"width":.08,"tool":"eraser"}]})

    def test_client_cannot_supply_owner_or_model_urls(self):
        for extra in ({"user_id":USER_B},{"endpoints":{"image":"https://attacker.invalid"}}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                JobRequest(request_id=uuid4(),kind="generate",prompt="heart",**extra)

    def test_invalid_label_coordinates_rejected(self):
        with self.assertRaises(ValueError):
            Annotation(structure_id="manual.1",label="Heart",anchor_x=float("nan"),anchor_y=.5,label_x=.1,label_y=.2)

    def test_nonfinite_evaluation_is_not_accepted(self):
        with self.assertRaises(ValueError):
            evaluation_result({"visual_score":float("nan"),"pedagogical_score":8})

    def test_models_are_resolved_on_server(self):
        with patch.dict(os.environ,{"IMAGE_AGENT_URL":"https://workspace-a.example"},clear=True):
            self.assertEqual(configured_endpoints(),{"image":"https://workspace-a.example"})
        self.assertEqual(required_services({"kind":"sketch"}),{"sketch"})

class OwnershipApiTests(unittest.TestCase):
    def test_unauthenticated_requests_cannot_clear_feedback(self):
        app.dependency_overrides.clear()
        try:
            with patch("studio.main.repo") as repo:
                response = self.client.request("DELETE","/feedback",json={"agent_name":"image-agent","output_id":"chosen-output"})
                self.assertEqual(response.status_code,401)
                repo.clear_feedback.assert_not_called()
        finally:
            app.dependency_overrides[require_user] = lambda: USER_B

    def test_feedback_deselection_uses_authenticated_owner_and_only_selected_output(self):
        with patch("studio.main.repo") as repo:
            repo.clear_feedback.return_value = {"status":"removed"}
            response = self.client.request("DELETE","/feedback",json={"agent_name":"image-agent","output_id":"chosen-output"})
            self.assertEqual(response.status_code,200)
            repo.clear_feedback.assert_called_once_with(USER_B,"image-agent","chosen-output")
            self.assertEqual(self.client.request("DELETE","/feedback",json={"agent_name":"image-agent","output_id":"chosen-output","user_id":USER_A}).status_code,422)

    def test_completed_model_link_does_not_download_large_assets_on_cpu_api(self):
        generation_id = str(uuid4())
        with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
            repo.get_history.return_value = {"id":generation_id,"glb_path":"owned/model.glb","metadata":{"glbSizeKb":120}}
            storage.return_value.signed_url.return_value = "https://private.example/model"
            response = self.client.get(f"/studio/history/{generation_id}/model")
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()["modelKey"],"owned/model.glb")
            repo.get_history.assert_called_once_with(USER_B,generation_id)
            storage.return_value.download.assert_not_called()
            repo.get_history.return_value = None
            self.assertEqual(self.client.get(f"/studio/history/{generation_id}/model").status_code,404)

    def test_url_history_returns_metadata_without_retransferring_image_and_model(self):
        from datetime import datetime, timezone
        generation_id = str(uuid4())
        with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
            repo.get_history.return_value = {"id":generation_id,"user_id":USER_B,"created_at":datetime.now(timezone.utc),
                "metadata":{},"image_path":"owned/image.png","glb_path":"owned/model.glb"}
            repo.get_interactions.return_value = []
            storage.return_value.signed_url.side_effect = lambda value: "https://private.example/"+value
            response = self.client.get(f"/studio/history/{generation_id}?asset_mode=urls")
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()["imageBase64"],"")
            self.assertIn("glbUrl",response.json())
            storage.return_value.download.assert_not_called()

    def test_gallery_is_private_and_signs_models_without_loading_binaries(self):
        from datetime import datetime, timezone
        generation_id = str(uuid4())
        with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
            repo.list_models.return_value = [{"id":"model-event","generation_id":generation_id,"chat_id":"chat", "title":"Skull",
                "created_at":datetime.now(timezone.utc),"mode":"anatomy","glb_path":"owned/skull.glb"}]
            storage.return_value.signed_url.return_value = "https://private.example/model"
            response = self.client.get("/studio/models?query=skull")
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()[0]["generationId"],generation_id)
            repo.list_models.assert_called_once_with(USER_B,None,"","skull",False)
            storage.return_value.download.assert_not_called()

    def setUp(self):
        app.dependency_overrides[require_user] = lambda: USER_B
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_missing_token_cannot_read_cloud_history(self):
        app.dependency_overrides.clear()
        self.assertEqual(self.client.get("/studio/history").status_code,401)

    def test_job_lookup_uses_authenticated_owner(self):
        job_id = str(uuid4())
        with patch("studio.main.repo") as repo:
            repo.get_job.return_value = None
            response = self.client.get("/studio/jobs/"+job_id)
            self.assertEqual(response.status_code,404)
            repo.get_job.assert_called_once_with(USER_B,job_id)

    def test_public_job_does_not_expose_payload_endpoints_or_handles(self):
        job_id = str(uuid4())
        with patch("studio.main.repo") as repo:
            repo.get_job.return_value = {"id":job_id,"status":"running","payload":{"prompt":"private"},
                "endpoints":{"image":"private"},"state":{"call_id":"private"},"lease_token":"private"}
            response = self.client.get("/studio/jobs/"+job_id)
            self.assertEqual(response.status_code,200)
            for field in ("payload","endpoints","state","lease_token"):
                self.assertNotIn(field,response.json())

    def test_manual_label_edits_mark_history_to_protect_from_late_autolabels(self):
        generation_id = str(uuid4())
        with patch("studio.main.repo") as repo:
            response = self.client.patch("/studio/history/"+generation_id,json={"anatomyAnnotations":[]})
            self.assertEqual(response.status_code,200)
            repo.patch_history.assert_called_once_with(USER_B,generation_id,{"anatomyAnnotations":[],"annotationsEdited":True})

class WorkflowRegressionTests(unittest.TestCase):
    def test_label_version_keeps_answer_snapshot_without_reassigning_original_events(self):
        from studio.schemas import HistoryImport
        from studio.main import import_history
        answers = [{"id":"original-question","answer":"Saved answer"}]
        with patch("studio.main.repo") as repo, patch("studio.main.Storage"):
            repo.get_history.return_value = None
            result = import_history(HistoryImport(legacy_id="new-label-version", created_at="2026-10-19T00:00:00Z",
                metadata={"mode":"general","chatId":"original-chat","interactions":answers},
                image_base64="aW1hZ2U=", snapshot_interactions=True), USER_A)
            saved = repo.save_history.call_args.args
            self.assertEqual(saved[1], result["id"])
            self.assertEqual(saved[2]["chatId"], "original-chat")
            self.assertEqual(saved[2]["interactions"], answers)
            repo.append_interaction.assert_not_called()
            repo.patch_history.assert_not_called()

    def test_bad_history_cursor_is_rejected_before_database_access(self):
        app.dependency_overrides[require_user] = lambda: USER_A
        try:
            with patch("studio.main.repo") as repo:
                self.assertEqual(TestClient(app).get("/studio/history?before=invalid").status_code,422)
                repo.list_history.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_failed_quality_retry_preserves_the_completed_image(self):
        repo,storage=Mock(),Mock()
        repo.heartbeat.return_value=True
        pipeline=Pipeline(repo=repo,storage=storage)
        pipeline.invoke=Mock(side_effect=[
            {"image_base64":"first-image"},
            {"visual_score":4,"pedagogical_score":4},
            RuntimeError("GPU unavailable"),
        ])
        job={"id":str(uuid4()),"user_id":USER_A,"kind":"generate","state":{},"endpoints":{},
            "payload":{"mode":"anatomy","prompt":"heart","speed_mode":"pro","auto_label":False}}
        pipeline.generate(job)
        self.assertEqual(storage.upload.call_args.args[1],"first-image")
        metadata=repo.save_history.call_args.args[2]
        self.assertIn("best completed image",metadata["evaluationWarning"])

    def test_import_retry_can_finish_the_missing_3d_upload(self):
        from studio.schemas import HistoryImport
        from studio.main import import_history
        with patch("studio.main.repo") as repo,patch("studio.main.Storage") as storage:
            repo.get_history.return_value={"metadata":{"chatId":"old-chat"},"image_path":"saved.png","glb_path":None}
            storage.return_value.upload.return_value="saved.glb"
            result=import_history(HistoryImport(legacy_id="old-item",created_at="2026-10-08T00:00:00Z",
                metadata={"mode":"sketch"},image_base64="aW1hZ2U=",glb_base64="Z2xi"),USER_A)
            storage.return_value.upload.assert_called_once()
            repo.patch_history.assert_called_once_with(USER_A,result["id"],{},glb_path="saved.glb")

class RecoveryTests(unittest.TestCase):
    def job(self):
        return {"id":str(uuid4()),"user_id":USER_A,"kind":"sketch","state":{},"lease_token":str(uuid4()),"endpoints":{"sketch":"https://workspace-a.example"}}

    def test_saved_modal_handle_is_polled_without_starting_a_second_generation(self):
        import time
        job = self.job()
        job["state"]={"call_id":"original-handle","call_started":time.time()}
        repo = Mock()
        pipeline = Pipeline(repo=repo,storage=Mock())
        response=Mock(status_code=200)
        response.json.return_value={"image_base64":"generated"}
        with patch("studio.pipeline.requests.get",return_value=response) as get, patch("studio.pipeline.requests.post") as post:
            self.assertEqual(pipeline.async_model(job,"sketch",{}),{"image_base64":"generated"})
            post.assert_not_called()
            self.assertIn("workspace-a.example/generate/result/original-handle",get.call_args.args[0])

    def test_waiting_3d_does_not_block_drawing_and_labels_or_exceed_worker_slots(self):
        import queue
        import threading
        from studio.worker import run_worker
        jobs = queue.Queue()
        for kind in ("threed", "sketch", "labels", "generate"):
            jobs.put({**self.job(), "kind": kind})
        repo, pipeline = Mock(), Mock()
        repo.claim.side_effect = lambda: jobs.get_nowait() if not jobs.empty() else None
        shutdown, release = threading.Event(), threading.Event()
        started = queue.Queue()
        def run(job):
            started.put(job["kind"])
            release.wait(5)
            return {"history_id": "saved-result"}
        pipeline.run.side_effect = run
        worker = threading.Thread(target=run_worker, args=(repo, pipeline, shutdown, 3))
        worker.start()
        try:
            self.assertEqual({started.get(timeout=2) for _ in range(3)}, {"threed", "sketch", "labels"})
            self.assertEqual(repo.claim.call_count, 3)
            self.assertEqual(jobs.qsize(), 1)
        finally:
            shutdown.set()
            release.set()
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(repo.update_job.call_count, 3)

    def test_uncertain_synchronous_call_is_not_blindly_replayed(self):
        job=self.job();job["state"]={"inflight":"image-0"}
        pipeline=Pipeline(repo=Mock(),storage=Mock())
        with patch("studio.pipeline.requests.post") as post,self.assertRaisesRegex(RuntimeError,"interrupted"):
            pipeline.invoke(job,"image","/generate",{},"image-0")
        post.assert_not_called()

    def test_worker_persists_completed_result_and_clears_large_checkpoint(self):
        repo,pipeline=Mock(),Mock()
        pipeline.run.return_value={"history_id":"result"}
        job=self.job()
        process_job(repo,pipeline,job)
        repo.update_job.assert_called_with(job,status="completed",stage="completed",result={"history_id":"result"},state={})

    def test_worker_failure_is_persisted_for_retry(self):
        repo,pipeline=Mock(),Mock()
        pipeline.run.side_effect=RuntimeError("Sketch service unavailable")
        job=self.job()
        process_job(repo,pipeline,job)
        repo.update_job.assert_called_with(job,status="failed",stage="failed",error="Sketch service unavailable")


class ThreeDPollingTests(unittest.TestCase):
    def setUp(self):
        self.job = {"id": str(uuid4()), "state": {"call_id": "fc-original", "call_started": 0},
                    "endpoints": {"threed": "https://gpu.example"}}
        self.repo = Mock()
        self.pipeline = Pipeline(repo=self.repo, storage=Mock())

    def result(self, status=200, **payload):
        response = Mock(status_code=status)
        response.json.return_value = payload
        return response

    def test_a_running_60_minute_gpu_call_is_not_discarded_at_55_minutes(self):
        result = self.result(glb_base64="model")
        with patch("studio.pipeline.time.time", return_value=3601), patch("studio.pipeline.requests.get", return_value=result):
            self.assertEqual(self.pipeline.async_model(self.job, "threed", {}), {"glb_base64": "model"})

    def test_recovered_worker_retrieves_an_already_completed_result_after_deadline(self):
        with patch("studio.pipeline.time.time", return_value=5000), patch("studio.pipeline.requests.get", return_value=self.result(glb_base64="model")), patch("studio.pipeline.requests.post") as post:
            self.assertEqual(self.pipeline.async_model(self.job, "threed", {})["glb_base64"], "model")
            post.assert_not_called()

    def test_pending_job_eventually_fails_instead_of_polling_forever(self):
        with patch("studio.pipeline.time.time", return_value=5000), patch("studio.pipeline.requests.get", return_value=self.result(202)), patch("studio.pipeline.time.sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "processing deadline"):
                self.pipeline.async_model(self.job, "threed", {})
            sleep.assert_not_called()

    def test_transient_poll_failure_does_not_discard_the_gpu_job(self):
        import requests
        with patch("studio.pipeline.time.time", return_value=100), patch("studio.pipeline.requests.get", side_effect=[requests.Timeout(), self.result(glb_base64="model")]), patch("studio.pipeline.time.sleep"):
            self.assertEqual(self.pipeline.async_model(self.job, "threed", {})["glb_base64"], "model")

    def test_stage_changes_are_persisted_without_repeating_the_same_update(self):
        responses = [self.result(202, stage="synthesizing texture"), self.result(202, stage="synthesizing texture"), self.result(glb_base64="model")]
        with patch("studio.pipeline.time.time", return_value=100), patch("studio.pipeline.requests.get", side_effect=responses), patch("studio.pipeline.time.sleep"):
            self.pipeline.async_model(self.job, "threed", {})
        self.repo.update_job.assert_called_once_with(self.job, stage="synthesizing texture")

    def test_pending_modal_call_does_not_claim_inference_has_started(self):
        responses = [self.result(202), self.result(glb_base64="model")]
        with patch("studio.pipeline.time.time", return_value=100), patch("studio.pipeline.requests.get", side_effect=responses), patch("studio.pipeline.time.sleep"):
            self.pipeline.async_model(self.job, "threed", {})
        self.repo.update_job.assert_called_once_with(self.job, stage="waiting for 3D service")

    def test_terminal_model_error_preserves_diagnostic_stage(self):
        response = self.result(500, error="3D conversion failed while synthesizing texture: out of memory")
        with patch("studio.pipeline.time.time", return_value=100), patch("studio.pipeline.requests.get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "synthesizing texture: out of memory"):
                self.pipeline.async_model(self.job, "threed", {})

if __name__ == "__main__":
    unittest.main()


class OutputFeedbackApiTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[require_user]=lambda: USER_A
        self.client=TestClient(app)
        self.payload={"session_id":"study","agent_name":"image-agent","output_id":"image","rating":-1}

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_rating_saves_locally_with_authenticated_owner_without_model_call(self):
        with patch("studio.main.repo") as repo,patch("studio.main.requests.post") as external:
            repo.save_feedback.return_value={"status":"recorded","feedback_id":str(uuid4())}
            response=self.client.post("/feedback",json=self.payload)
            self.assertEqual(response.status_code,201)
            self.assertEqual(repo.save_feedback.call_args.args[0],USER_A)
            self.assertEqual(repo.save_feedback.call_args.args[1]["rating"],-1)
            external.assert_not_called()
            app.dependency_overrides.clear()
            self.assertEqual(self.client.post("/feedback",json=self.payload).status_code,401)

    def test_owner_spoofing_invalid_rating_and_oversized_context_are_rejected(self):
        with patch("studio.main.repo") as repo:
            for changes in ({"auth_user_id":USER_B},{"rating":0},{"input_context":{"text":"x"*10001}}):
                self.assertEqual(self.client.post("/feedback",json={**self.payload,**changes}).status_code,422)
            repo.save_feedback.assert_not_called()

    def test_another_accounts_output_cannot_be_overwritten(self):
        with patch("studio.main.repo") as repo:
            repo.save_feedback.side_effect=LookupError("Foreign output")
            self.assertEqual(self.client.post("/feedback",json=self.payload).status_code,404)
