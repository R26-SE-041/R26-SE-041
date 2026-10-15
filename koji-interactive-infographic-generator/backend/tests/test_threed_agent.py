"""3D orchestration regressions; no GPU, downloads or Modal credentials needed."""
import base64
from contextlib import nullcontext
import importlib.util
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from PIL import Image


def load_agent():
    modal = Mock()
    decorate = lambda *args, **kwargs: lambda wrapped: wrapped
    modal.enter.side_effect = decorate
    modal.method.side_effect = decorate
    modal.asgi_app.side_effect = decorate
    modal.App.return_value.cls.side_effect = decorate
    modal.App.return_value.function.side_effect = decorate
    modal.Dict.from_name.side_effect = lambda *args, **kwargs: {}
    modal.current_function_call_id.return_value = "fc-test"
    path = Path(__file__).parents[1] / "agents/threed-agent/modal_app.py"
    spec = importlib.util.spec_from_file_location("threed_agent_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"modal": modal, spec.name: module}):
        spec.loader.exec_module(module)
    return module


class ThreeDAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_agent()

    def setUp(self):
        self.module.conversion_jobs.clear()
        self.module.conversion_progress.clear()
        self.module.modal.FunctionCall.from_id.reset_mock(side_effect=True)
        self.image = io.BytesIO()
        Image.new("RGBA", (16, 16), "red").save(self.image, format="PNG")
        self.image_bytes = self.image.getvalue()
        self.agent = self.module._ThreeDAgentBase()
        self.mesh = SimpleNamespace(faces=range(120_000), export=Mock(return_value=b"glTF-model"))
        self.reduced = SimpleNamespace(faces=range(40_000), export=Mock(return_value=b"glTF-textured"))
        self.agent.shape_pipe = Mock(return_value=[self.mesh])
        self.agent.tex_pipe = Mock(return_value=self.reduced)
        self.reducer = Mock(return_value=self.reduced)
        self.shapegen = SimpleNamespace(FaceReducer=Mock(return_value=self.reducer))
        torch = Mock()
        torch.inference_mode.side_effect = nullcontext
        self.modules = patch.dict(sys.modules, {"torch": torch, "hy3dgen.shapegen": self.shapegen})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        background = patch.object(self.module, "remove_background", return_value=self.image_bytes)
        background.start()
        self.addCleanup(background.stop)

    def test_dense_mesh_is_reduced_before_paint_and_export(self):
        calls = Mock()
        calls.attach_mock(self.agent.shape_pipe, "shape")
        calls.attach_mock(self.reducer, "reduce")
        calls.attach_mock(self.agent.tex_pipe, "paint")
        result = self.agent.convert(self.image_bytes)
        self.assertIsNone(result["error"])
        self.assertEqual(result["glb_bytes"], b"glTF-textured")
        self.assertEqual([call[0] for call in calls.mock_calls], ["shape", "reduce", "paint"])
        self.reducer.assert_called_once_with(self.mesh, max_facenum=40_000)
        self.agent.tex_pipe.assert_called_once_with(self.reduced, image=unittest.mock.ANY)
        self.assertEqual(self.agent.shape_pipe.call_args.kwargs["octree_resolution"], 256)

    def test_small_mesh_skips_reduction(self):
        self.mesh.faces = range(10_000)
        self.agent.convert(self.image_bytes)
        self.reducer.assert_not_called()
        self.agent.tex_pipe.assert_called_once_with(self.mesh, image=unittest.mock.ANY)

    def test_shape_only_skips_reduction_and_texture(self):
        result = self.agent.convert(self.image_bytes, texture=False)
        self.assertEqual(result["glb_bytes"], b"glTF-model")
        self.reducer.assert_not_called()
        self.agent.tex_pipe.assert_not_called()

    def test_failed_reduction_does_not_start_expensive_uv_processing(self):
        self.reducer.return_value = self.mesh
        result = self.agent.convert(self.image_bytes)
        self.assertIn("simplifying mesh", result["error"])
        self.assertIsNone(result["glb_bytes"])
        self.agent.tex_pipe.assert_not_called()

    def test_texture_failure_never_returns_an_untextured_success(self):
        self.agent.tex_pipe.side_effect = RuntimeError("paint failed")
        result = self.agent.convert(self.image_bytes)
        self.assertIn("synthesizing texture: paint failed", result["error"])
        self.assertIsNone(result["glb_bytes"])
        self.mesh.export.assert_not_called()

    def test_empty_shape_is_rejected_before_paint(self):
        self.mesh.faces = []
        result = self.agent.convert(self.image_bytes)
        self.assertIn("empty mesh", result["error"])
        self.agent.tex_pipe.assert_not_called()

    def test_invalid_glb_is_rejected(self):
        self.reduced.export.return_value = b"not a model"
        result = self.agent.convert(self.image_bytes)
        self.assertIn("valid GLB", result["error"])
        self.assertIsNone(result["glb_bytes"])

    def test_progress_failure_does_not_break_inference(self):
        with patch.object(self.module, "conversion_progress") as progress:
            progress.__setitem__.side_effect = RuntimeError("telemetry unavailable")
            self.assertIsNone(self.agent.convert(self.image_bytes)["error"])

    def test_pipeline_resolution_matches_both_renderer_and_config(self):
        shape_loader, paint_loader = Mock(), Mock()
        self.shapegen.Hunyuan3DDiTFlowMatchingPipeline = shape_loader
        paint = paint_loader.from_pretrained.return_value
        paint.models = {"delight": Mock(), "multiview": Mock()}
        with patch.dict(sys.modules, {"hy3dgen.texgen": SimpleNamespace(Hunyuan3DPaintPipeline=paint_loader)}):
            self.agent.load_pipelines()
        self.assertEqual(paint_loader.from_pretrained.call_args.kwargs["subfolder"], "hunyuan3d-paint-v2-0-turbo")
        self.assertEqual(paint.config.render_size, 1024)
        self.assertEqual(paint.config.texture_size, 1024)
        paint.render.set_default_render_resolution.assert_called_once_with(1024)
        paint.render.set_default_texture_resolution.assert_called_once_with(1024)
        self.assertEqual(paint.render.bake_unreliable_kernel_size, 4)

    def test_pending_result_includes_actual_stage(self):
        self.module.modal.FunctionCall.from_id.return_value.get.side_effect = TimeoutError
        self.module.conversion_progress["fc-pending"] = {"stage": "synthesizing texture"}
        response = TestClient(self.module.web_app).get("/convert/result/fc-pending")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["stage"], "synthesizing texture")

    def test_completed_inference_failure_is_failed_http_response(self):
        call = self.module.modal.FunctionCall.from_id.return_value
        call.get.side_effect = None
        call.get.return_value = {"glb_bytes": None, "error": "paint failed"}
        response = TestClient(self.module.web_app).get("/convert/result/fc-failed")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["error"], "paint failed")

    def test_retry_replaces_a_completed_call_that_returned_an_error(self):
        self.module.conversion_jobs["request-one"] = "fc-failed"
        call = self.module.modal.FunctionCall.from_id.return_value
        call.get.side_effect = None
        call.get.return_value = {"glb_bytes": None, "error": "paint failed"}
        worker = Mock()
        worker.convert.spawn.return_value.object_id = "fc-new"
        with patch.object(self.module, "_agent_for_mode", return_value=worker):
            response = TestClient(self.module.web_app).post("/convert/start", json={
                "image_base64": base64.b64encode(self.image_bytes).decode(), "request_id": "request-one",
            })
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["call_id"], "fc-new")
        self.assertFalse(response.json()["reused"])
        worker.convert.spawn.assert_called_once()

    def test_retry_reuses_a_running_call_instead_of_spawning_again(self):
        self.module.conversion_jobs["request-one"] = "fc-running"
        self.module.modal.FunctionCall.from_id.return_value.get.side_effect = TimeoutError
        with patch.object(self.module, "_agent_for_mode") as route:
            response = TestClient(self.module.web_app).post("/convert/start", json={
                "image_base64": base64.b64encode(self.image_bytes).decode(), "request_id": "request-one",
            })
        self.assertTrue(response.json()["reused"])
        route.assert_not_called()

    def test_bad_images_and_invalid_steps_are_rejected_before_gpu_work(self):
        client = TestClient(self.module.web_app)
        with patch.object(self.module, "_agent_for_mode") as route:
            for encoded in ("", "not base64!", base64.b64encode(b"not an image").decode()):
                self.assertEqual(client.post("/convert/start", json={"image_base64": encoded}).status_code, 400)
            for steps in (0, 101):
                self.assertEqual(client.post("/convert/start", json={
                    "image_base64": base64.b64encode(self.image_bytes).decode(), "num_inference_steps": steps,
                }).status_code, 422)
            route.assert_not_called()


class BackgroundRemovalTests(unittest.TestCase):
    def test_existing_transparency_is_preserved_without_loading_an_onnx_model(self):
        module = load_agent()
        image = io.BytesIO()
        Image.new("RGBA", (16, 16), (255, 0, 0, 0)).save(image, format="PNG")
        with patch.dict(sys.modules, {"rembg": Mock()}), patch.object(module, "background_session") as session:
            self.assertEqual(module.remove_background(image.getvalue()), image.getvalue())
            session.assert_not_called()

    def test_onnx_session_is_reused_and_uses_cpu(self):
        module = load_agent()
        rembg = Mock()
        with patch.dict(sys.modules, {"rembg": rembg}):
            self.assertIs(module.background_session(), module.background_session())
        rembg.new_session.assert_called_once_with("u2net", providers=["CPUExecutionProvider"])
