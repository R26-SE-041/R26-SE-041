import unittest

from orchestrator.graph import reflection_node, should_retry
from shared.state import initial_state


class ReflectionAcceptTests(unittest.TestCase):
    def test_accepts_when_scores_clear_threshold(self) -> None:
        state = initial_state("a heart")
        state["visual_score"] = 8.0
        state["pedagogical_score"] = 7.5
        state["image_bytes"] = b"png-bytes"

        result = reflection_node(state)

        self.assertIsNone(result["retry_feedback"])
        self.assertEqual(result["visual_score"], 8.0)
        self.assertEqual(result["pedagogical_score"], 7.5)

    def test_retries_when_a_score_is_below_threshold(self) -> None:
        state = initial_state("a heart")
        state["visual_score"] = 5.0
        state["pedagogical_score"] = 8.0
        state["image_bytes"] = b"png-bytes"

        result = reflection_node(state)

        self.assertIsNotNone(result["retry_feedback"])
        self.assertEqual(result["retry_count"], 1)

    def test_retries_on_anatomy_hard_failure_even_with_high_scores(self) -> None:
        state = initial_state("a heart")
        state["visual_score"] = 9.0
        state["pedagogical_score"] = 9.0
        state["image_bytes"] = b"png-bytes"
        state["anatomy_hard_failures"] = ["missing left ventricle"]

        result = reflection_node(state)

        self.assertIsNotNone(result["retry_feedback"])
        self.assertIn("ANATOMY HARD FAILURES", result["retry_feedback"])

    def test_stops_retrying_after_two_attempts_and_keeps_best(self) -> None:
        state = initial_state("a heart")
        state["visual_score"] = 3.0
        state["pedagogical_score"] = 3.0
        state["image_bytes"] = b"worse-attempt"
        state["retry_count"] = 2
        state["best_attempt"] = {
            "visual_score": 8.0,
            "pedagogical_score": 8.0,
            "image_bytes": b"best-attempt",
            "anatomy_hard_failures": [],
        }

        result = reflection_node(state)

        self.assertIsNone(result["retry_feedback"])
        self.assertEqual(result["image_bytes"], b"best-attempt")

    def test_missing_image_bytes_forces_accept_of_best_attempt(self) -> None:
        # image_node/eval_node failed to produce an image this attempt, so no
        # scores were computed either — current_total stays below best_total.
        state = initial_state("a heart")
        state["image_bytes"] = None
        state["best_attempt"] = {
            "visual_score": 6.0,
            "pedagogical_score": 6.0,
            "image_bytes": b"earlier-attempt",
            "anatomy_hard_failures": [],
        }

        result = reflection_node(state)

        self.assertIsNone(result["retry_feedback"])
        self.assertEqual(result["image_bytes"], b"earlier-attempt")

    def test_reflexion_disabled_always_accepts(self) -> None:
        state = initial_state("a heart")
        state["visual_score"] = 1.0
        state["pedagogical_score"] = 1.0
        state["image_bytes"] = b"png-bytes"
        state["experiment_config"] = {"enable_reflexion": False}

        result = reflection_node(state)

        self.assertIsNone(result["retry_feedback"])


class ShouldRetryRoutingTests(unittest.TestCase):
    def test_accepts_when_no_retry_feedback(self) -> None:
        state = initial_state("a heart")
        self.assertEqual(should_retry(state), "accept")

    def test_accepts_when_reflexion_disabled(self) -> None:
        state = initial_state("a heart")
        state["retry_feedback"] = "some feedback"
        state["experiment_config"] = {"enable_reflexion": False}
        self.assertEqual(should_retry(state), "accept")

    def test_routes_to_retry_image_for_anatomy_prompts(self) -> None:
        state = initial_state("a heart")
        state["retry_feedback"] = "some feedback"
        state["anatomy_spec"] = {"is_anatomy": True}
        self.assertEqual(should_retry(state), "retry_image")

    def test_routes_to_retry_prompt_for_generic_prompts(self) -> None:
        state = initial_state("a sunset")
        state["retry_feedback"] = "some feedback"
        state["anatomy_spec"] = {"is_anatomy": False}
        self.assertEqual(should_retry(state), "retry_prompt")


if __name__ == "__main__":
    unittest.main()
