import copy
import json
import unittest
from unittest.mock import patch

import app.graph.graph  # noqa: F401
from app.agents.quiz_agent import (
    _historical_duplicate_reason,
    _difficulty_candidate_rejection,
    _make_fallback_topic_question,
    _previous_learner_questions,
    _semantic_duplicate_reason,
    _universal_topic_fallback,
    _validate_mcq,
    quiz_agent,
)
from app.services.db_service import DbService
from app.services.biology_recovery import BANK, reviewed_source_candidates


def state(mode="easy", topic="Photosystem", documents=False):
    return {
        "session_id": "fresh-session", "student_id": "learner",
        "document_ids": ["biology.pdf"] if documents else [],
        "requested_topic": None if documents else topic,
        "chroma_collection_id": "fresh-session", "topics": [topic],
        "questions": [], "quiz_blueprint": [], "agent_logs": [],
        "flagged_questions": [], "current_q_index": 0, "num_questions": 1,
        "exam_type": "mcq", "difficulty_mode": mode, "current_difficulty": .8,
    }


class RetakeAndDifficultyTests(unittest.TestCase):
    def test_retakes_allow_new_applications_of_a_familiar_fact(self):
        previous = {"question": "Which organelle modifies proteins received from the ER?", "options": {"1": "Golgi apparatus"}, "correct_answer": "1"}
        fresh = {**previous, "question": "After secretory proteins leave ER normally but fail to reach the membrane, which sorting compartment should be investigated?"}
        self.assertFalse(_historical_duplicate_reason(fresh, [previous]))
        self.assertTrue(_historical_duplicate_reason(previous, [previous]))

    def test_reviewed_questions_match_difficulty_and_do_not_use_unrelated_sources(self):
        self.assertEqual(reviewed_source_candidates([{"text": "Enterprise application transaction management."}], "hard"), [])
        for topic, words, levels in BANK:
            for level in levels:
                pool = reviewed_source_candidates([{"chunk_id": "source", "text": " ".join(words)}], level)
                for candidate, anchor in pool:
                    with self.subTest(topic=topic, level=level, question=candidate["question"]):
                        _validate_mcq(copy.deepcopy(candidate))
                        self.assertFalse(_difficulty_candidate_rejection(candidate, level))
                        self.assertEqual(anchor["chunk_id"], candidate["_source_anchor_id"])

    def test_exact_recovery_stems_cannot_bypass_duplicate_checks(self):
        old = {
            "question": 'A learner must analyze the relationship in "Golgi apparatus". Which topic should be integrated first?',
            "options": {"1": "Golgi apparatus"}, "correct_answer": "1",
            "_source_recovery": True,
        }
        candidate = {**old, "question": old["question"].upper()}
        self.assertIn("identical", _semantic_duplicate_reason(candidate, [old]))

    def test_generic_bank_exhaustion_does_not_cycle_to_first_question(self):
        from app.agents.quiz_agent import _GENERIC_TOPIC_FALLBACK
        self.assertIsNone(_make_fallback_topic_question(
            "Biology", _GENERIC_TOPIC_FALLBACK, .8, "hard"
        ))

    @patch("app.agents.quiz_agent._wikipedia_topic_material", return_value=("", "", ()))
    def test_universal_fallback_never_repeats_its_fixed_template(self, wiki):
        first = _universal_topic_fallback("Protein", [], "hard")
        self.assertIsNotNone(first)
        self.assertIsNone(_universal_topic_fallback("Protein", [first], "hard"))

    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_fixed_easy_and_medium_start_at_the_selected_level(self, llm, db):
        llm.return_value.check_health.return_value = False
        db.return_value.get_previous_questions.return_value = []
        for mode, difficulty in (("easy", .2), ("medium", .5), ("hard", .8)):
            with self.subTest(mode=mode):
                result = quiz_agent(state(mode))
                self.assertIsNone(result.get("error"))
                question = result["questions"][0]
                self.assertEqual(question["difficulty"], difficulty)
                self.assertFalse(_difficulty_candidate_rejection(question, mode))
        llm.return_value.call_json.assert_not_called()

    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_retakes_never_select_the_previous_local_question(self, llm, db):
        llm.return_value.check_health.return_value = False
        db.return_value.get_previous_questions.return_value = []
        first = quiz_agent(state("hard"))["questions"][0]
        db.return_value.get_previous_questions.return_value = [first]
        second_state = state("hard")
        second_state["session_id"] = "second-session"
        second = quiz_agent(second_state)
        self.assertIsNone(second.get("error"))
        self.assertFalse(_semantic_duplicate_reason(second["questions"][0], [first]))

    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.LlmService")
    @patch("app.agents.quiz_agent._wikipedia_topic_material", return_value=("", "", ()))
    def test_exhausted_topic_returns_error_without_persisting_a_duplicate(self, wiki, llm, db):
        llm.return_value.check_health.return_value = False
        llm.return_value.call_json.side_effect = RuntimeError("Model offline")
        previous = _universal_topic_fallback("Protein", [], "hard")
        db.return_value.get_previous_questions.return_value = [previous]
        result = quiz_agent(state("hard", "Protein"))
        self.assertTrue(result.get("error"))
        self.assertEqual(result["questions"], [])
        db.return_value.save_question.assert_not_called()

    @patch("app.agents.quiz_agent.DbService")
    def test_generation_requests_history_without_a_120_question_cutoff(self, db):
        db.return_value.get_previous_questions.return_value = []
        _previous_learner_questions(state(), "mcq")
        self.assertIsNone(db.return_value.get_previous_questions.call_args.kwargs["limit"])

    def test_hard_and_medium_reject_recall_dressed_as_a_scenario(self):
        question = {"question": 'While analysing proteins, evidence shows "_____ are biomolecules". Which concept must be integrated first to explain this result?'}
        for level in ("hard", "medium"):
            self.assertTrue(_difficulty_candidate_rejection(question, level))
        self.assertFalse(_difficulty_candidate_rejection(
            {"question": "Which pigment forms the reaction centre of photosystem II?"}, "easy"
        ))
        self.assertTrue(_difficulty_candidate_rejection(
            {"question": "After an inhibitor blocks electron flow, which experimental outcome is predicted?"}, "easy"
        ))

    @patch("app.services.db_service.DB_PATH", ":memory:")
    @patch("app.services.db_service.os.makedirs")
    def test_persisted_history_retains_old_questions_and_isolates_learners(self, mkdir):
        db = DbService()
        try:
            db.conn.executemany(
                "INSERT INTO sessions (session_id, student_id) VALUES (?, ?)",
                [("old", "learner"), ("current", "learner"), ("other", "someone-else")],
            )
            rows = [(f"q{i}", "old", "mcq", f"Historical question {i}", json.dumps({"1": "Fact"})) for i in range(130)]
            rows += [("current-q", "current", "mcq", "Current question", "null"),
                     ("other-q", "other", "mcq", "Someone else's question", "null")]
            db.conn.executemany(
                "INSERT INTO questions (q_id, session_id, q_type, question_text, options_json) VALUES (?, ?, ?, ?, ?)", rows,
            )
            db.conn.commit()
            history = db.get_previous_questions("learner", exclude_session_id="current", q_type="mcq", limit=None)
            self.assertEqual(len(history), 130)
            self.assertIn("Historical question 0", [q["question"] for q in history])
        finally:
            db.conn.close()


class DocumentRetakeTests(unittest.TestCase):
    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.GroundingService")
    @patch("app.agents.quiz_agent.RagService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_unkeyed_paper_has_reviewed_recovery_when_model_and_embedding_gate_fail(self, llm, rag, grounding, db):
        chunk = {"chunk_id": "exam", "text": "Which statements about the human lymphatic system are correct? Lymphatic vessels bear valves, and lymph nodes contain immune cells.", "source": "exam.pdf", "page": 1, "distance": .05}
        rag.return_value.get_source_chunks.return_value = [chunk]
        rag.return_value.retrieve.return_value = [chunk]
        llm.return_value.check_health.return_value = False
        grounding.return_value.score.return_value = .429
        grounding.return_value.threshold = .55
        db.return_value.get_previous_questions.return_value = []
        paper_state = state("hard", "Lymphatic system", documents=True)
        paper_state["quiz_blueprint"] = [{"concept": "Lymphatic system", "source_chunk_id": "exam", "difficulty": .8}]
        result = quiz_agent(paper_state)
        self.assertIsNone(result.get("error"))
        self.assertEqual(result["questions"][0]["grounding_status"], "topic_model")
        self.assertEqual(result["questions"][0]["grounding_score"], .429)
        self.assertEqual(result["questions"][0]["difficulty"], .8)
        llm.return_value.call_json.assert_not_called()

    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.GroundingService")
    @patch("app.agents.quiz_agent.RagService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_document_easy_mode_and_history_rejection_apply_to_fallbacks(self, llm, rag, grounding, db):
        chunk = {
            "chunk_id": "chlorophyll", "source": "biology.pdf", "page": 1,
            "distance": .05, "text": "Chlorophyll absorbs light energy during photosynthesis. Chlorophyll a occurs in the reaction centres of photosystems, which use absorbed energy for electron transport.",
        }
        candidate = {
            "question": "Which pigment absorbs light energy during photosynthesis?",
            "options": {"1": "Chlorophyll", "2": "Haemoglobin", "3": "Melanin", "4": "Keratin", "5": "Collagen"},
            "correct_answer": "1", "model_answer": "Chlorophyll absorbs light energy during photosynthesis.",
        }
        slot = {"concept": "Photosynthesis", "concept_focus": chunk["text"], "source_chunk_id": "chlorophyll", "difficulty": .8}
        doc_state = state("easy", "Photosynthesis", documents=True)
        doc_state["quiz_blueprint"] = [slot]
        rag.return_value.get_source_chunks.return_value = [chunk]
        rag.return_value.retrieve.return_value = [chunk]
        llm.return_value.check_health.return_value = True
        llm.return_value.call_json.return_value = {"questions": [copy.deepcopy(candidate)]}
        db.return_value.get_previous_questions.return_value = []
        audit = {"grounding_score": .9, "grounding_status": "grounded", "evidence_chunk_id": "chlorophyll"}
        with patch("app.agents.quiz_agent._embedding_grounding_audit", return_value=audit), \
             patch("app.agents.quiz_agent.build_concept_plan", return_value=[slot]), \
             patch("app.agents.quiz_agent._source_fallback_mcq", return_value=copy.deepcopy(candidate)):
            first = quiz_agent(copy.deepcopy(doc_state))
            self.assertIsNone(first.get("error"))
            self.assertEqual(first["questions"][0]["difficulty"], .2)
            db.return_value.get_previous_questions.return_value = [candidate]
            db.return_value.save_question.reset_mock()
            second = quiz_agent(copy.deepcopy(doc_state))
            self.assertTrue(second.get("error"))
            db.return_value.save_question.assert_not_called()


if __name__ == "__main__":
    unittest.main()
