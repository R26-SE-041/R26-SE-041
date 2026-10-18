import os
import unittest
from unittest.mock import patch

from app.deployment_config import allowed_origins
from app.services.db_service import DbService
from app.services.postgres_connection import PostgresConnection


class ConfigurationTests(unittest.TestCase):
    def test_production_requires_database_and_exact_https_origins(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "DATABASE_URL": ""}, clear=True):
            with self.assertRaises(RuntimeError):
                allowed_origins()
            os.environ["ALLOWED_ORIGINS"] = "https://quiz.vercel.app"
            with self.assertRaises(RuntimeError):
                allowed_origins()
            os.environ["DATABASE_URL"] = "postgresql://unused"
            self.assertEqual(allowed_origins(), ["https://quiz.vercel.app"])
            for origin in ("*", "https://*.vercel.app", "http://quiz.vercel.app", "https://quiz.vercel.app/path", "https://quiz.vercel.app?x=1"):
                os.environ["ALLOWED_ORIGINS"] = origin
                with self.subTest(origin=origin), self.assertRaises(RuntimeError):
                    allowed_origins()

    def test_multiple_origins_and_development_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn("http://localhost:3000", allowed_origins())
            os.environ["ALLOWED_ORIGINS"] = " https://quiz.vercel.app/, https://preview.vercel.app "
            self.assertEqual(allowed_origins(), ["https://quiz.vercel.app", "https://preview.vercel.app"])


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"DATABASE_URL": ""})
        self.env.start()
        self.path = patch("app.services.db_service.DB_PATH", ":memory:")
        self.path.start()
        self.db = DbService()

    def tearDown(self):
        self.db.conn.close()
        self.path.stop()
        self.env.stop()

    def test_assessment_lifecycle_and_upserts_preserve_answers(self):
        db = self.db
        db.conn.execute("PRAGMA foreign_keys=ON")
        db.save_document({"document_id": "d", "filename": "bio.pdf", "topics": "[]", "chunk_count": 1})
        db.save_document({"document_id": "d", "filename": "biology.pdf", "topics": '["cells"]', "chunk_count": 2})
        self.assertEqual(db.get_documents(["d"])[0]["filename"], "biology.pdf")
        self.assertEqual(db.get_documents([]), [])
        db.create_session(dict(session_id="s", student_id="learner", exam_type="mcq", num_questions=1,
                               difficulty_mode="easy", time_limit_min=10, status="ready",
                               chroma_collection_id="d", is_topic_session=0))
        question = dict(q_id="q", session_id="s", q_index=0, topic="cells", bloom_level="remember",
                        difficulty=0.2, q_type="mcq", question_text="What is a cell?", options_json='{"1":"unit"}',
                        correct_answer="1", model_answer="", grounding_score=1.0, is_flagged=0,
                        source_file="bio.pdf", page_number=1, retrieved_text="cell", grounding_status="accepted")
        db.save_question(question)
        db.save_answer(dict(answer_id="a", session_id="s", q_id="q", student_answer="1", is_correct=1,
                            score=1.0, attempt_number=1, hints_used=0, time_taken_sec=4, feedback="Correct", misconception=""))
        db.save_question({**question, "question_text": "Updated question"})
        self.assertEqual(db.conn.execute("SELECT count(*) FROM answers").fetchone()[0], 1)
        db.update_session_progress("s", ["cells"], 2)
        db.save_feedback("s", 5, "Helpful")
        db.update_session_status("s", "completed")
        self.assertEqual(db.get_session("s")["rating"], 5)
        self.assertEqual(db.get_session("s")["status"], "completed")
        self.assertEqual(db.get_previous_questions("learner")[0]["question"], "Updated question")
        self.assertEqual(db.get_previous_questions("other"), [])
        report = dict(session_id="s", final_score=1.0, topic_scores="{}", bloom_scores="{}",
                      difficulty_progression="[]", weak_topics="[]", strong_topics="[]", recommendations="[]",
                      avg_grounding_score=1.0, flagged_count=0, avg_attempts=1, avg_hints_used=0, total_time_sec=4)
        db.save_analytics(report)
        db.save_analytics({**report, "final_score": 0.9})
        self.assertEqual(db.get_analytics("s")["final_score"], 0.9)
        db.log_event("s", "quiz", "completed")


class PostgresTransactionTests(unittest.TestCase):
    @patch("app.services.postgres_connection._pool")
    def test_bound_parameters_and_buffered_results(self, pool_factory):
        pool = pool_factory.return_value
        connection = pool.getconn.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = [("session_id",)]
        cursor.fetchall.return_value = [{"session_id": "s"}]
        db = PostgresConnection()
        self.assertEqual(db.execute("SELECT session_id FROM sessions WHERE student_id=?", ("untrusted ' input",)).fetchone(), {"session_id": "s"})
        cursor.execute.assert_called_with("SELECT session_id FROM sessions WHERE student_id=%s", ("untrusted ' input",))
        pool.putconn.assert_called_once_with(connection)
        db.execute("UPDATE sessions SET status=:status WHERE session_id=:id", {"status": "ready", "id": "s"})
        cursor.execute.assert_called_with("UPDATE sessions SET status=%(status)s WHERE session_id=%(id)s", {"status": "ready", "id": "s"})

    @patch("app.services.postgres_connection._pool")
    def test_failed_statement_releases_transaction_and_connection(self, pool_factory):
        pool = pool_factory.return_value
        connection = pool.getconn.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = RuntimeError("constraint violation")
        with self.assertRaises(RuntimeError):
            PostgresConnection().execute("INSERT INTO sessions VALUES (?)", ("s",))
        self.assertEqual(connection.__exit__.call_args.args[0], RuntimeError)
        pool.putconn.assert_called_once_with(connection)


if __name__ == "__main__":
    unittest.main()
