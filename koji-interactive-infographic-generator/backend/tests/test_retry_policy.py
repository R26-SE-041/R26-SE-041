from unittest.mock import Mock
from uuid import uuid4

import pytest
from studio.pipeline import Pipeline
from studio.schemas import JobRequest


def run_generation(scores):
    repo, storage = Mock(), Mock()
    repo.heartbeat.return_value = True
    pipeline = Pipeline(repo, storage)
    evaluations = iter(scores)
    count = 0

    def invoke(job, service, path, payload, key):
        nonlocal count
        if service == "image":
            count += 1
            return {"image_base64": f"image-{count}", "generation_metadata": {}}
        visual, educational, failures = next(evaluations)
        return {"visual_score": visual, "pedagogical_score": educational, "anatomy_hard_failures": failures}

    pipeline.invoke = Mock(side_effect=invoke)
    pipeline.generate({"id": str(uuid4()), "user_id": "owner", "kind": "generate", "state": {}, "endpoints": {},
        "payload": {"prompt": "heart", "mode": "anatomy", "speed_mode": "normal", "anatomy": {"is_anatomy": True}, "auto_label": False, "chat_id": "original-chat"}})
    return count, repo.save_history.call_args.args[2], storage.upload.call_args.args[1]


def test_average_output_is_accepted_without_spending_on_another_image():
    count, metadata, image = run_generation([(5, 5, [])])
    assert count == 1
    assert metadata["evaluationRetries"] == 0
    assert metadata["chatId"] == "original-chat"
    assert image == "image-1"


def test_critical_failure_retries_even_with_a_high_cosmetic_score():
    count, metadata, image = run_generation([(9, 9, ["wrong organ"]), (6, 6, [])])
    assert count == 2
    assert metadata["evaluationRetries"] == 1
    assert image == "image-2"


def test_at_most_two_retries_then_keep_best_completed_output():
    count, metadata, image = run_generation([(3, 3, []), (4, 4, []), (2, 2, [])])
    assert count == 3
    assert metadata["evaluationRetries"] == 2
    assert image == "image-2"


@pytest.mark.parametrize("prompt", ["pornographic image", "educational nude woman", "sexualized model", "erotic anatomy illustration"])
def test_sexual_prompts_are_rejected_before_a_job_can_be_queued(prompt):
    with pytest.raises(ValueError, match="CONTENT_POLICY_BLOCKED"):
        JobRequest(request_id=uuid4(), kind="generate", prompt=prompt)


def test_nonsexual_anatomy_still_passes_the_request_gate():
    request = JobRequest(request_id=uuid4(), kind="generate", prompt="anterior view of a human heart")
    assert request.prompt == "anterior view of a human heart"
