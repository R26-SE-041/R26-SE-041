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
            {"visual_score":5,"pedagogical_score":6},
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

if __name__ == "__main__":
    unittest.main()
