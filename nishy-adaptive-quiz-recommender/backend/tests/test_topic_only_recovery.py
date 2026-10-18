import copy
import unittest
from unittest.mock import patch

import app.graph.graph  # noqa: F401
from app.agents.quiz_agent import (
    _TOPIC_FALLBACK_BANK,
    _difficulty_candidate_rejection,
    _historical_duplicate_reason,
    _validate_mcq,
    quiz_agent,
)
from app.services.topic_practice import reviewed_topic_bank


class TopicOnlyRecoveryTests(unittest.TestCase):
    def test_every_reviewed_lipid_question_passes_format_and_difficulty_checks(self):
        for question in reviewed_topic_bank("Lipids"):
            with self.subTest(question=question["question"]):
                _validate_mcq(copy.deepcopy(question))
                self.assertFalse(_difficulty_candidate_rejection(question, question["_difficulty"]))

    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.LlmService")
    @patch("app.agents.quiz_agent._universal_topic_fallback")
    def test_ten_questions_work_with_old_lipid_history_and_a_timing_out_model(self, universal, llm, db):
        history = [q for key, bank in _TOPIC_FALLBACK_BANK if key in "lipids" for q in bank]
        db.return_value.get_previous_questions.return_value = history
        llm.return_value.check_health.return_value = True
        llm.return_value.call_json.side_effect = RuntimeError("Modal inference timed out after 5s")
        for mode, difficulty in (("adaptive", .8), ("medium", .5), ("easy", .2)):
            with self.subTest(mode=mode):
                state = {
                    "session_id": f"lipids-{mode}", "student_id": "learner",
                    "requested_topic": "Lipids", "document_ids": [],
                    "exam_type": "mcq", "num_questions": 10, "questions": [],
                    "difficulty_mode": mode, "current_difficulty": difficulty,
                    "quiz_blueprint": [], "agent_logs": [], "flagged_questions": [],
                }
                stems = []
                for index in range(10):
                    state["current_q_index"] = index
                    generated = quiz_agent(state)
                    self.assertIsNone(generated.get("error"))
                    state.update(generated)
                    question = state["questions"][-1]
                    self.assertEqual(question["topic"], "Lipids")
                    self.assertEqual(question["difficulty"], difficulty)
                    self.assertFalse(_historical_duplicate_reason(question, history))
                    stems.append(question["question"])
                self.assertEqual(len(set(stems)), 10)
        llm.return_value.check_health.assert_not_called()
        llm.return_value.call_json.assert_not_called()
        universal.assert_not_called()

    def test_topic_aliases_and_unrelated_subjects_do_not_share_a_bank(self):
        self.assertTrue(reviewed_topic_bank("  LIPIDS "))
        self.assertTrue(reviewed_topic_bank("fats and oils"))
        self.assertEqual(reviewed_topic_bank("Java EE"), [])


if __name__ == "__main__":
    unittest.main()
