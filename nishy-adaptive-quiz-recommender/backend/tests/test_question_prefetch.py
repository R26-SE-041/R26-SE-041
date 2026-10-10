import unittest
from unittest.mock import Mock, patch

from app.services.question_prefetch import prefetch_next_question


class QuestionPrefetchTests(unittest.TestCase):
    @patch("app.services.question_prefetch.quiz_agent")
    @patch("app.services.question_prefetch.get_graph")
    def test_prefetch_publishes_one_question_without_advancing_live_index(
        self, get_graph, quiz_agent
    ):
        graph = Mock()
        graph.get_state.return_value.values = {
            "session_id": "s1",
            "current_q_index": 0,
            "num_questions": 3,
            "difficulty_mode": "hard",
            "exam_type": "mcq",
            "questions": [{"q_id": "q1"}],
            "quiz_blueprint": [],
        }
        get_graph.return_value = graph
        quiz_agent.return_value = {
            "questions": [{"q_id": "q1"}, {"q_id": "q2"}],
            "quiz_blueprint": [{}, {}],
            "agent_logs": [],
            "error": None,
        }

        prefetch_next_question("s1")

        generation_state = quiz_agent.call_args.args[0]
        self.assertEqual(generation_state["current_q_index"], 1)
        published = graph.update_state.call_args.args[1]
        self.assertNotIn("current_q_index", published)
        self.assertEqual(published["questions"][-1]["q_id"], "q2")

    @patch("app.services.question_prefetch.quiz_agent")
    @patch("app.services.question_prefetch.get_graph")
    def test_prefetch_skips_when_buffer_already_exists(self, get_graph, quiz_agent):
        graph = Mock()
        graph.get_state.return_value.values = {
            "current_q_index": 0,
            "num_questions": 3,
            "questions": [{"q_id": "q1"}, {"q_id": "q2"}],
        }
        get_graph.return_value = graph

        prefetch_next_question("s1")

        quiz_agent.assert_not_called()
        graph.update_state.assert_not_called()

    @patch("app.services.question_prefetch.quiz_agent")
    @patch("app.services.question_prefetch.get_graph")
    def test_adaptive_mcq_never_prefetches_before_current_attempt_is_known(
        self, get_graph, quiz_agent
    ):
        graph = Mock()
        graph.get_state.return_value.values = {
            "current_q_index": 1,
            "num_questions": 5,
            "difficulty_mode": "adaptive",
            "exam_type": "mcq",
            "current_difficulty": 0.8,
            "questions": [{"q_id": "q1"}, {"q_id": "q2"}],
        }
        get_graph.return_value = graph

        prefetch_next_question("s1")

        quiz_agent.assert_not_called()
        graph.update_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
