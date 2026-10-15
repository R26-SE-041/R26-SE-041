"""Sketch HTTP and renderer wiring without CUDA or model downloads."""
import base64
from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np
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
    path = Path(__file__).parents[1] / "agents/sketch-agent/modal_app.py"
    spec = importlib.util.spec_from_file_location("sketch_agent_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"modal": modal, spec.name: module}):
        spec.loader.exec_module(module)
    return module


class SketchAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_agent()

    def setUp(self):
        self.client = TestClient(self.module.web_app)
        self.request = {"strokes": [{"points": [[.2, .5], [.8, .5]]}], "seed": 42}

    def test_blank_request_never_starts_gpu_orchestrator(self):
        with patch.object(self.module.generate_sketch, "spawn", create=True) as spawn:
            response = self.client.post("/generate/start", json={"strokes": []})
            self.assertEqual(response.status_code, 422)
            spawn.assert_not_called()

    def test_async_endpoint_uses_complete_pipeline(self):
        with patch.object(self.module.generate_sketch, "spawn", create=True) as spawn:
            spawn.return_value.object_id = "fc-sketch"
            response = self.client.post("/generate/start", json=self.request)
            self.assertEqual(response.json(), {"call_id": "fc-sketch"})
            self.assertEqual(spawn.call_args.args[0]["seed"], 42)

    def test_completed_clarification_remains_actionable(self):
        lookup = self.module.modal.FunctionCall.from_id
        lookup.return_value.get.return_value = {
            "error": "Eye or leaf? Add the subject in Additional instruction.",
            "error_code": "clarification_required"}
        response = self.client.get("/generate/result/fc-sketch")
        self.assertEqual(response.json()["error_code"], "clarification_required")

    def test_renderer_concatenates_all_prompt_chunks_and_uses_control_release(self):
        renderer = self.module.SketchRenderer()
        tokenizer = Mock(model_max_length=7)
        tokenizer.encode.side_effect = lambda value: value.split() + [0, 0]
        pipe = Mock()
        pipe.tokenizer = pipe.tokenizer_2 = tokenizer
        pipe.encode_prompt.return_value = (
            np.ones((2, 7, 4)), np.zeros((2, 7, 4)), np.ones((2, 4)), np.zeros((2, 4)))
        pipe.return_value.images = [Image.new("RGB", (16, 16), "orange")]
        renderer.pipe = pipe
        torch = Mock()
        torch.inference_mode.side_effect = nullcontext
        with patch.dict(sys.modules, {"torch": torch}):
            result = renderer.generate(self.request, "Full color human eye white background complete shape soft shading",
                                       42, {"control_strength": .68, "control_guidance_end": .65})
        self.assertEqual(pipe.call_args.kwargs["prompt_embeds"].shape, (1, 14, 4))
        self.assertEqual(pipe.call_args.kwargs["negative_prompt_embeds"].shape, (1, 14, 4))
        self.assertEqual(pipe.call_args.kwargs["controlnet_conditioning_scale"], .68)
        self.assertEqual(pipe.call_args.kwargs["control_guidance_end"], .65)
        self.assertEqual(result["generation_metadata"]["prompt_chunks"], 2)
        self.assertTrue(base64.b64decode(result["image_base64"]).startswith(b"\x89PNG"))
