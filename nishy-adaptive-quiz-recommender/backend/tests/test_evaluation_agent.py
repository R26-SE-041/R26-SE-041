import unittest
from unittest.mock import Mock, patch

# Import through the graph package first because its package initializer owns
# the application's agent import order.
import app.graph.graph  # noqa: F401
from app.agents.evaluation_agent import (
    _normalize_exact_answer,
    _generate_hint,
    _is_repetitive_or_malformed,
    _reveals_mcq_answer,
    evaluation_agent,
)


class FillBlankAnswerTests(unittest.TestCase):
    def test_exact_answer_ignores_only_case_spacing_and_terminal_punctuation(self):
        self.assertEqual(_normalize_exact_answer("  Golgi   Apparatus. "), "golgi apparatus")
        self.assertNotEqual(_normalize_exact_answer("Golgi body"), "golgi apparatus")


QUESTION = {
    "q_id": "q1",
    "q_type": "mcq",
    "question": "Which component owns the request lifecycle?",
    "topic": "Java EE",
    "bloom_level": "apply",
    "correct_answer": "2",
    "options": {
        "1": "A presentation-only helper",
        "2": "The web container",
        "3": "A database index",
        "4": "A build-time compiler",
        "5": "A deployment descriptor",
    },
    "model_answer": "The web container manages the relevant server-side request lifecycle.",
}


class HintSafetyTests(unittest.TestCase):
    def test_rejects_runaway_repetition(self):
        broken = "Java EE API layers repeat the same phrase " * 30
        self.assertTrue(_is_repetitive_or_malformed(broken))

    def test_rejects_direct_answer_letter_and_text(self):
        self.assertTrue(_reveals_mcq_answer("Choose option 2.", QUESTION))
        self.assertTrue(_reveals_mcq_answer("The web container owns it.", QUESTION))
        self.assertFalse(
            _reveals_mcq_answer(
                "Separate lifecycle ownership from presentation and persistence responsibilities.",
                QUESTION,
            )
        )

    def test_retries_bad_output_then_returns_safe_hint(self):
        llm = Mock()
        llm.call.side_effect = [
            "Java EE API layers repeat the same phrase " * 30,
            "The answer is 2.",
            "Separate lifecycle ownership from presentation concerns. Then identify which runtime boundary manages a request from entry to completion.",
        ]
        rag = Mock()
        rag.retrieve.return_value = [{
            "text": "Java EE separates container responsibilities for the request lifecycle.",
            "distance": 0.1,
        }]

        hint = _generate_hint(llm, rag, QUESTION, 0, "collection")

        self.assertEqual(llm.call.call_count, 3)
        self.assertNotIn("answer is", hint.casefold())
        self.assertFalse(_is_repetitive_or_malformed(hint))

    def test_uses_safe_fallback_after_three_rejected_outputs(self):
        llm = Mock()
        llm.call.return_value = "Choose option 2."
        rag = Mock()
        rag.retrieve.return_value = [{
            "text": "Java EE separates container responsibilities for the request lifecycle.",
            "distance": 0.1,
        }]

        hint = _generate_hint(llm, rag, QUESTION, 2, "collection")

        self.assertEqual(llm.call.call_count, 3)
        self.assertFalse(_reveals_mcq_answer(hint, QUESTION))


class AttemptFlowTests(unittest.TestCase):
    @staticmethod
    def _state(previous_answers, pending="1"):
        return {
            "session_id": "session-1",
            "questions": [QUESTION],
            "current_q_index": 0,
            "num_questions": 1,
            "answers": previous_answers,
            "_pending_answer": pending,
            "_answer_time_sec": 5,
            "chroma_collection_id": "collection",
            "topic_scores": {},
            "bloom_scores": {},
            "agent_logs": [],
        }

    @patch("app.agents.evaluation_agent.RagService")
    @patch("app.agents.evaluation_agent.LlmService")
    def test_fourth_wrong_attempt_reveals_answer_and_explanation(self, _llm, _rag):
        previous = [
            {"q_id": "q1", "attempts": n, "is_correct": False, "hints_used": n}
            for n in (1, 2, 3)
        ]

        result = evaluation_agent(self._state(previous))["answers"][-1]

        self.assertEqual(result["attempts"], 4)
        self.assertEqual(result["hints_used"], 3)
        self.assertIn("**The web container**", result["feedback"])
        self.assertNotIn("**2 —", result["feedback"])
        self.assertEqual(result["correct_answer"], "2")
        self.assertEqual(result["correct_answer_text"], "The web container")
        self.assertEqual(
            result["explanation"],
            "The web container manages the relevant server-side request lifecycle.",
        )
        self.assertIn("**Detailed Explanation:**", result["feedback"])

    @patch("app.agents.evaluation_agent.RagService")
    @patch("app.agents.evaluation_agent.LlmService")
    def test_correct_retry_retains_number_of_hints_used(self, _llm, _rag):
        previous = [
            {"q_id": "q1", "attempts": n, "is_correct": False, "hints_used": n}
            for n in (1, 2)
        ]

        result = evaluation_agent(self._state(previous, pending="2"))["answers"][-1]

        self.assertTrue(result["is_correct"])
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["hints_used"], 2)
        self.assertIn("**The web container**", result["feedback"])
        self.assertNotIn("**2 —", result["feedback"])
        self.assertEqual(result["correct_answer"], "2")
        self.assertEqual(result["correct_answer_text"], "The web container")
        self.assertEqual(
            result["explanation"],
            "The web container manages the relevant server-side request lifecycle.",
        )
        self.assertIn("**Detailed Explanation:**", result["feedback"])

    @patch("app.agents.evaluation_agent.generate_adaptive_hint")
    @patch("app.agents.evaluation_agent.RagService")
    @patch("app.agents.evaluation_agent.LlmService")
    def test_attempt_state_selects_medium_and_passes_hard_history(
        self, _llm, _rag, generate_hint
    ):
        generate_hint.return_value = "A validated medium Biology hint."
        previous = [
            {
                "q_id": "q1",
                "attempts": 1,
                "is_correct": False,
                "hints_used": 1,
                "hint": "A validated hard Biology hint.",
                "feedback": "Incorrect.",
            }
        ]

        result = evaluation_agent(self._state(previous, pending="1"))["answers"][-1]

        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["hint_level"], "MEDIUM")
        self.assertEqual(result["hint"], "A validated medium Biology hint.")
        self.assertEqual(
            generate_hint.call_args.kwargs["previous_hints"],
            ["A validated hard Biology hint."],
        )

    @patch("app.agents.evaluation_agent.generate_adaptive_hint")
    @patch("app.agents.evaluation_agent.RagService")
    @patch("app.agents.evaluation_agent.LlmService")
    def test_open_ended_response_keeps_retry_and_returns_adaptive_hint(
        self, llm_cls, _rag, generate_hint
    ):
        llm_cls.return_value.call_json.return_value = {
            "score": 0.35,
            "is_correct": False,
            "feedback": "The response identifies one relevant relationship.",
        }
        question = {
            **QUESTION,
            "q_type": "structured",
            "model_answer": "A complete source-grounded explanation of the biological relationships.",
            "marks_breakdown": {"facts": 50, "reasoning": 50},
        }
        state = self._state([], pending="A partial extended response")
        state["questions"] = [question]

        generate_hint.return_value = "A source-grounded structured-answer hint."

        update = evaluation_agent(state)
        result = update["answers"][-1]

        self.assertEqual(update["current_q_index"], 0)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["hint"], "A source-grounded structured-answer hint.")
        self.assertNotIn("Detailed Explanation", result["feedback"])


if __name__ == "__main__":
    unittest.main()
