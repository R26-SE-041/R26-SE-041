import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
import app.graph.graph  # noqa: F401
from app.routers import quiz


class RetryGenerationTests(unittest.TestCase):
    @patch.object(quiz, "submit_session_work")
    @patch.object(quiz, "get_graph")
    @patch.object(quiz, "db")
    def test_retry_recovers_stale_processing_and_only_queues_one_job(self, db, graph, submit):
        db.get_session.return_value = {"status": "processing"}
        graph.return_value.get_state.return_value.values = {"questions": [], "current_q_index": 0, "error": "Old setup failed"}
        submit.return_value.done.return_value = False
        with patch.dict(quiz._retry_jobs, {}, clear=True):
            self.assertEqual(quiz.retry_question_generation("failed"), {"status": "processing"})
            self.assertEqual(quiz.retry_question_generation("failed"), {"status": "processing"})
        submit.assert_called_once_with("failed", quiz._retry_generation, "failed")

    @patch.object(quiz, "submit_session_work")
    @patch.object(quiz, "get_graph")
    @patch.object(quiz, "db")
    def test_retry_preserves_an_existing_active_question(self, db, graph, submit):
        db.get_session.return_value = {"status": "error"}
        graph.return_value.get_state.return_value.values = {"questions": [{"q_id": "existing"}], "current_q_index": 0}
        self.assertEqual(quiz.retry_question_generation("ready"), {"status": "ready"})
        submit.assert_not_called()

    @patch.object(quiz, "db")
    def test_unknown_session_is_not_recreated(self, db):
        db.get_session.return_value = None
        with self.assertRaises(HTTPException) as exc:
            quiz.retry_question_generation("unknown")
        self.assertEqual(exc.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
