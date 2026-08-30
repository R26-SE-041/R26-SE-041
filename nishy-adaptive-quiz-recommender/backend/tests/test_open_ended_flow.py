import unittest
from unittest.mock import Mock, patch

import app.graph.graph  # noqa: F401
from app.agents.analytics_agent import analytics_agent
from app.routers.quiz import advance_open_ended_question
from app.schemas.quiz import AdvanceQuestionRequest


QUESTION = {
    "q_id": "structured-1",
    "q_type": "structured",
    "question": "(a) Explain the relationship. (b) Apply it to the observation.",
    "topic": "Transport",
    "bloom_level": "apply",
    "difficulty": 0.5,
    "model_answer": "A complete source-supported model answer for both labelled parts.",
}


class OpenEndedAdvanceTests(unittest.TestCase):
    @patch("app.routers.quiz.submit_session_work")
    @patch("app.routers.quiz.get_graph")
    def test_next_finalizes_partial_answer_and_advances(self, get_graph, submit_work):
        graph = Mock()
        graph.get_state.return_value.values = {
            "session_id": "session",
            "questions": [QUESTION, {**QUESTION, "q_id": "structured-2"}],
            "current_q_index": 0,
            "num_questions": 2,
            "answers": [{
                "q_id": "structured-1",
                "student_answer": "A partial answer",
                "is_correct": False,
                "score": 0.35,
                "attempts": 1,
                "hints_used": 1,
                "time_taken_sec": 20,
                "feedback": "A useful adaptive hint.",
                "misconception": None,
            }],
            "topic_scores": {},
            "bloom_scores": {},
        }
        get_graph.return_value = graph

        response = advance_open_ended_question(
            "session", AdvanceQuestionRequest(q_id="structured-1")
        )

        update = graph.update_state.call_args.args[1]
        self.assertEqual(update["current_q_index"], 1)
        self.assertTrue(update["_skip_requested"])
        self.assertTrue(update["answers"][-1]["is_terminal"])
        self.assertEqual(update["topic_scores"]["Transport"]["total"], 1)
        self.assertFalse(response.quiz_complete)
        self.assertIn("Detailed Explanation", response.result.feedback)
        submit_work.assert_called_once()


class OpenEndedAnalyticsTests(unittest.TestCase):
    def test_structured_partial_credit_uses_mcq_style_hundred_mark_report(self):
        state = {
            "session_id": "results",
            "questions": [QUESTION],
            "answers": [{
                "q_id": "structured-1",
                "student_answer": "A partial answer",
                "is_correct": False,
                "is_terminal": True,
                "score": 0.35,
                "attempts": 1,
                "hints_used": 1,
                "time_taken_sec": 20,
            }],
            "topic_scores": {"Transport": {"correct": 0, "total": 1}},
            "bloom_scores": {"apply": {"correct": 0, "total": 1}},
            "flagged_questions": [],
            "agent_logs": [],
        }

        report = analytics_agent(state)["analytics_report"]

        self.assertEqual(report["total_marks_earned"], 35)
        self.assertEqual(report["total_marks_possible"], 100)
        self.assertEqual(report["question_marks_detail"][0]["marks"], 35)


if __name__ == "__main__":
    unittest.main()
