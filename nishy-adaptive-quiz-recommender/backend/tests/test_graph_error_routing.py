import unittest

from langgraph.graph import END

from app.agents.error_handler import error_handler_node
from app.graph.graph import route_after_error, route_after_evaluation


class GenerationErrorRoutingTests(unittest.TestCase):
    def test_explicit_next_routes_incorrect_essay_forward(self):
        state = {
            "answers": [{"q_id": "essay-1", "is_correct": False, "attempts": 1}],
            "questions": [{"q_id": "essay-1", "q_type": "essay"}],
            "current_q_index": 1,
            "num_questions": 3,
            "_skip_requested": True,
        }

        self.assertEqual(route_after_evaluation(state), "adaptive")

    def test_retries_a_mid_quiz_generation_error(self):
        state = {"retry_count": 2, "current_q_index": 3, "num_questions": 5}

        self.assertEqual(route_after_error(state), "quiz_generate")

    def test_exhausted_mid_quiz_error_does_not_become_analytics_completion(self):
        state = {"retry_count": 3, "current_q_index": 3, "num_questions": 5}

        self.assertEqual(route_after_error(state), END)

    def test_final_retry_preserves_the_generation_error(self):
        result = error_handler_node({
            "error": "Could not generate a complete valid quiz.",
            "retry_count": 2,
            "agent_logs": [],
        })

        self.assertEqual(result["retry_count"], 3)
        self.assertIn("Could not generate", result["error"])


if __name__ == "__main__":
    unittest.main()
