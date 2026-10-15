"""Durable sketch results must retain the same anatomy/quality contract as HTTP."""
from unittest.mock import Mock

from studio.pipeline import Pipeline


def test_cloud_sketch_preserves_anatomy_quality_and_editable_strength():
    repo, storage = Mock(), Mock()
    repo.heartbeat.return_value = True
    pipeline = Pipeline(repo, storage)
    anatomy = {"is_anatomy": True, "organ": "eye", "view_description": "external view"}
    pipeline.async_model = Mock(return_value={
        "image_base64": "coloured-eye", "prompt": "Full-color human eye on white",
        "anatomy_spec": anatomy, "quality_warning": "Inspect proportions", "retry_count": 1,
        "generation_metadata": {"subject": "human eye", "control_strength": .68}})
    job = {"id": "generation", "user_id": "owner", "kind": "sketch", "state": {}, "endpoints": {},
           "payload": {"mode": "sketch", "prompt": "", "speed_mode": "normal", "auto_label": False,
                       "sketch": {"strokes": [{"points": [[.2, .5], [.8, .5]]}], "control_strength": .85}}}
    pipeline.generate(job)
    record = repo.save_history.call_args.args[2]
    assert record["anatomy"] == anatomy
    assert record["enhancedPayload"]["route"] == "anatomy"
    assert record["sketchStrength"] == .85
    assert record["sketchMetadata"]["control_strength"] == .68
    assert record["evaluationRetries"] == 1
    assert record["evaluationWarning"] == "Inspect proportions"
    assert storage.upload.call_args.args[1] == "coloured-eye"
