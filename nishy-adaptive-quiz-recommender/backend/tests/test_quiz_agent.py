import unittest
from unittest.mock import Mock, patch

import app.graph.graph  # noqa: F401
from app.agents.quiz_agent import (
    _embedding_grounding_audit,
    _expand_source_combination_options,
    _semantic_duplicate_reason,
    _select_usable_chunks,
    _source_fallback_mcq,
    _validate_mcq,
    _infer_biology_topic,
    _make_fallback_topic_question,
    _record_from_candidate,
    _topic_candidate_rejection,
    _with_live_difficulty,
    build_blueprint,
    build_concept_plan,
    quiz_agent,
)


class FiveOptionMcqTests(unittest.TestCase):
    def test_reserve_plan_cannot_overwrite_live_easy_difficulty(self):
        stale_reserve = {"concept": "Golgi apparatus", "difficulty": 0.8}
        live = _with_live_difficulty(stale_reserve, 0.2)
        self.assertEqual(live["difficulty"], 0.2)
        self.assertEqual(stale_reserve["difficulty"], 0.8)

    def test_adaptive_record_ignores_stale_hard_plan_after_fourth_attempt(self):
        state = {
            "difficulty_mode": "adaptive",
            "current_difficulty": 0.2,
            "questions": [{"q_id": "previous"}],
        }
        slot = {"concept": "Golgi apparatus", "difficulty": 0.8}
        candidate = {
            "question": "Which Golgi relationship is supported?",
            "options": {str(i): f"Choice {i}" for i in range(1, 6)},
            "correct_answer": "1",
            "model_answer": "The source supports the first relationship.",
        }
        chunks = [{"chunk_id": "c1", "source": "biology.pdf", "page": 1, "text": "Golgi source."}]
        audit = {"evidence_chunk_id": "c1", "grounding_score": 0.8}
        record = _record_from_candidate(state, slot, candidate, chunks, audit)
        self.assertEqual(record["difficulty"], 0.2)
        self.assertEqual(record["bloom_level"], "remember")

    def test_rejects_direct_recall_question_labelled_hard(self):
        candidate = {
            "question": "Which level of biological organisation is immediately above the tissue level?",
            "options": {"1": "Photosystem", "2": "Organ", "3": "Cell", "4": "Tissue", "5": "Organism"},
            "correct_answer": "2",
            "model_answer": "This does not assess photosystem reasoning.",
        }
        self.assertIn("two-step", _topic_candidate_rejection(candidate, "Photosystem", "hard"))

    def test_photosystem_fallback_matches_requested_difficulty(self):
        hard = _make_fallback_topic_question("Photosystem", [], 0.8, "hard")
        easy = _make_fallback_topic_question("Photosystem", [], 0.2, "easy")
        self.assertEqual(hard["_difficulty"], "hard")
        self.assertIn("observations", hard["question"])
        self.assertEqual(easy["_difficulty"], "easy")

    def test_source_recovery_uses_correct_answer_as_topic_label(self):
        topic = _infer_biology_topic(
            {
                "question": 'A learner must analyze the relationship in "Golgi apparatus". Which topic should be integrated first?',
                "options": {"1": "Golgi apparatus"},
                "correct_answer": "1",
            },
            {"concept": "question paper item"},
        )

        self.assertEqual(topic, "Golgi apparatus")

    def test_uses_correct_source_topic_for_recovery_question(self):
        topic = _infer_biology_topic(
            {
                "question": 'Which biological topic is assessed by the focus "Golgi apparatus"?',
                "options": {"1": "Golgi apparatus"},
                "correct_answer": "1",
            },
            {"concept": "source recovery"},
        )

        self.assertEqual(topic, "Golgi apparatus")

    def test_infers_clean_biology_topic_from_generic_statement_stem(self):
        topic = _infer_biology_topic(
            {"question": "Which of these statements about cell features is correct?"},
            {"concept": "Basic features shared by all cells"},
        )

        self.assertEqual(topic, "cell features")

    def test_accepts_exactly_five_numeric_options(self):
        question = {
            "question": "Which statement is supported?",
            "options": {str(number): f"Option {number}" for number in range(1, 6)},
            "correct_answer": "5",
            "model_answer": "The source supports option five.",
        }

        self.assertIs(_validate_mcq(question), question)

    def test_rejects_four_options(self):
        question = {
            "options": {str(number): f"Option {number}" for number in range(1, 5)},
            "correct_answer": "4",
        }

        with self.assertRaisesRegex(ValueError, "exactly"):
            _validate_mcq(question)

    def test_rejects_answer_outside_one_through_five(self):
        question = {
            "question": "Which statement is supported?",
            "options": {str(number): f"Option {number}" for number in range(1, 6)},
            "correct_answer": "Z",
            "model_answer": "The source supports one listed option.",
        }

        with self.assertRaisesRegex(ValueError, "1.*5"):
            _validate_mcq(question)

    def test_rejects_explanation_that_names_a_different_option(self):
        question = {
            "question": "Hexose is a component of which polysaccharide?",
            "options": {
                "1": "Pectin",
                "2": "Chitin",
                "3": "Inulin",
                "4": "Hemicellulose",
                "5": "Cellulose",
            },
            "correct_answer": "3",
            "model_answer": "Pectin contains the stated hexose component.",
        }

        with self.assertRaisesRegex(ValueError, "contradicts"):
            _validate_mcq(question)

    def test_rejects_pdf_question_leaked_into_an_option(self):
        question = {
            "question": "Which statement correctly describes microscope resolution?",
            "options": {
                "1": "Which of the following is correct regarding the microscope?",
                "2": "Ability to distinguish two close points",
                "3": "Total size of the specimen",
                "4": "Brightness of the image",
                "5": "Width of the microscope stage",
            },
            "correct_answer": "2",
            "model_answer": "Resolution distinguishes two close points as separate structures in a microscopic image.",
        }

        with self.assertRaisesRegex(ValueError, "malformed"):
            _validate_mcq(question)

    def test_rejects_grammatically_broken_stem(self):
        question = {
            "question": "Which statement correctly describes regarding microscope?",
            "options": {str(number): f"Valid choice {number}" for number in range(1, 6)},
            "correct_answer": "1",
            "model_answer": "Valid choice one correctly identifies the required microscopy relationship and its defining property.",
        }

        with self.assertRaisesRegex(ValueError, "grammatically"):
            _validate_mcq(question)

    def test_normalizes_lettered_options_to_numeric_keys(self):
        question = {
            "question": "Which relationship is supported?",
            "options": {letter: f"Choice {letter}" for letter in "ABCDE"},
            "correct_answer": "C",
            "model_answer": "The source supports the third choice.",
        }

        normalized = _validate_mcq(question)

        self.assertEqual(set(normalized["options"]), {"1", "2", "3", "4", "5"})
        self.assertEqual(normalized["correct_answer"], "3")

    def test_normalizes_option_prefixed_keys_and_supplies_minimal_model_answer(self):
        question = {
            "question": "Which molecule is a monosaccharide?",
            "options": {f"Option {number}": value for number, value in enumerate(
                ["Glucose", "Starch", "Cellulose", "Protein", "Lipid"], start=1
            )},
            "correct_answer": "Option 1",
        }

        normalized = _validate_mcq(question)

        self.assertEqual(normalized["correct_answer"], "1")
        self.assertIn("Glucose", normalized["model_answer"])
        self.assertGreaterEqual(len(normalized["model_answer"].split()), 12)

    def test_supplies_grammatical_relationship_explanation_for_which_of_these(self):
        question = {
            "question": "Hexose is present as monosaccharide component in which of these?",
            "options": {
                "1": "Pectin",
                "2": "Chitin",
                "3": "Inulin",
                "4": "Hemicellulose",
                "5": "Cellulose",
            },
            "correct_answer": "1",
            "model_answer": "Pectin",
        }

        normalized = _validate_mcq(question)

        self.assertIn("Hexose occurs as monosaccharide component of Pectin", normalized["model_answer"])
        self.assertNotIn("the of these", normalized["model_answer"])

    def test_rejects_combination_choices_when_statements_are_missing(self):
        question = {
            "question": "Which combination correctly describes stomatal opening?",
            "options": {
                "1": "B and C only",
                "2": "A and C only",
                "3": "B and D only",
                "4": "B, C and D only",
                "5": "A and D only",
            },
            "correct_answer": "5",
            "model_answer": "A and D are correct.",
        }

        with self.assertRaisesRegex(ValueError, "missing"):
            _validate_mcq(question)

    def test_expands_label_only_combinations_from_pdf_statements(self):
        candidate = {
            "question": "Which statements correctly describe all cells?",
            "options": {
                "1": "A and B only",
                "2": "A and C only",
                "3": "B and C only",
                "4": "B and D only",
                "5": "C and D only",
            },
            "correct_answer": "1",
            "model_answer": "A and B are correct.",
        }
        chunks = [{
            "text": (
                "a) A plasma membrane encloses every cell. "
                "b) Every cell contains genetic material. "
                "c) Every cell has a cellulose wall. "
                "d) Every cell contains a nucleus. "
                "1) a and b 2) a and c 3) b and c"
            )
        }]

        expanded = _expand_source_combination_options(candidate, chunks)
        validated = _validate_mcq(expanded)

        self.assertIn("plasma membrane", validated["options"]["1"])
        self.assertNotEqual(validated["options"]["1"], "A and B only")

    def test_blueprint_does_not_create_general_topic_fallback(self):
        self.assertEqual(build_blueprint({"topics": [], "num_questions": 5}), [])

    def test_retrieval_gate_rejects_weak_chunks(self):
        chunks = [{
            "chunk_id": "weak",
            "text": "Biology source text " * 10,
            "source": "notes.pdf",
            "page": 2,
            "distance": 0.85,
        }]
        self.assertEqual(_select_usable_chunks(chunks), [])

    def test_rejects_reordered_lymphatic_option_fact_set_as_semantic_duplicate(self):
        first = {
            "question": "Which combination is correct for the human lymphatic system?",
            "options": {
                "1": "Valves, blind-ended capillaries, flow towards heart",
                "2": "Valves, open-ended capillaries, flow away from heart",
                "3": "No valves, blind-ended capillaries, flow towards heart",
                "4": "No valves, open-ended capillaries, flow away from heart",
                "5": "Valves, blind-ended capillaries, flow away from heart",
            },
            "correct_answer": "1",
            "model_answer": "Lymph vessels have valves and blind ends; lymph moves heartward.",
        }
        reordered = {
            "question": "Which statement correctly describes lymphatic capillaries, valves and flow?",
            "options": {
                "1": first["options"]["4"],
                "2": first["options"]["3"],
                "3": first["options"]["5"],
                "4": first["options"]["1"],
                "5": first["options"]["2"],
            },
            "correct_answer": "4",
            "model_answer": "Blind-ended lymphatics contain valves and carry lymph towards the heart.",
        }

        reason = _semantic_duplicate_reason(reordered, [first])

        self.assertTrue(reason)

    def test_concept_plan_uses_distinct_source_facts_before_reuse(self):
        chunks = [{
            "chunk_id": "bio-1",
            "text": (
                "Lymphatic capillaries are blind-ended and collect tissue fluid. "
                "Lymphatic vessels contain valves that maintain flow towards the heart. "
                "Lymph nodes filter lymph and contain immune cells."
            ),
            "source": "biology.pdf",
            "page": 4,
            "heading": "Lymphatic system",
        }]

        plan = build_concept_plan({"num_questions": 3, "exam_type": "mcq"}, chunks)

        self.assertEqual(len(plan), 3)
        self.assertEqual(len({item["concept_focus"] for item in plan}), 3)
        self.assertFalse(any(item.get("source_reuse_required") for item in plan))

    def test_source_only_recovery_produces_a_valid_direct_mcq(self):
        chunks = [{
            "chunk_id": "bio-1",
            "text": (
                "Lymphatic capillaries are blind-ended and collect tissue fluid. "
                "Nephrons filter blood and form urine in the kidney. "
                "Alveoli provide a large surface for gaseous exchange. "
                "Chlorophyll absorbs light energy during photosynthesis. "
                "Ribosomes synthesize proteins using messenger RNA."
            ),
            "source": "biology.pdf",
            "page": 1,
        }]
        slot = {"concept_focus": "Lymphatic capillaries are blind-ended and collect tissue fluid."}

        fallback = _source_fallback_mcq(slot, chunks, 0)

        self.assertIsNotNone(fallback)
        self.assertNotIn("combination", fallback["question"].casefold())
        self.assertEqual(_validate_mcq(fallback)["correct_answer"], "1")


class SourceGroundedPipelineTests(unittest.TestCase):
    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.GroundingService")
    @patch("app.agents.quiz_agent.RagService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_cold_modal_uses_analytical_source_recovery_without_setup_failure(
        self, llm_cls, rag_cls, grounding_cls, db_cls
    ):
        chunk = {
            "chunk_id": "evolution-1",
            "text": (
                "Sponges evolved. Ancestors of arthropods and chordates originated. "
                "Colonization of land by fungi plants and animals followed. "
                "Large tree forms differentiated into roots stems and leaves."
            ),
            "source": "biology.pdf",
            "page": 2,
            "heading": "Diversification of eukaryotes",
            "distance": 0.05,
        }
        llm_cls.return_value.check_health.return_value = False
        rag_cls.return_value.get_source_chunks.return_value = [chunk]
        rag_cls.return_value.retrieve.return_value = [chunk]
        grounding_cls.return_value.score.return_value = 0.50
        grounding_cls.return_value.threshold = 0.55
        state = {
            "session_id": "cold-source",
            "chroma_collection_id": "cold-source",
            "topics": ["Diversification of eukaryotes"],
            "num_questions": 1,
            "exam_type": "mcq",
            "difficulty_mode": "adaptive",
            "current_difficulty": 0.8,
            "current_q_index": 0,
            "questions": [],
            "quiz_blueprint": [],
            "flagged_questions": [],
            "agent_logs": [],
        }

        result = quiz_agent(state)

        self.assertIsNone(result.get("error"))
        self.assertEqual(len(result["questions"]), 1)
        self.assertIn("Fossil evidence", result["questions"][0]["question"])
        self.assertEqual(result["questions"][0]["difficulty"], 0.8)
        llm_cls.return_value.call_json.assert_not_called()
        db_cls.return_value.save_question.assert_called_once()

    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.GroundingService")
    @patch("app.agents.quiz_agent.RagService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_question_is_retrieved_validated_and_persisted_with_source_metadata(
        self, llm_cls, rag_cls, grounding_cls, db_cls
    ):
        chunk = {
            "chunk_id": "bio_p2_0",
            "text": "The source states that structure X performs function Y in the named process. " * 2,
            "source": "biology-notes.pdf",
            "page": 2,
            "heading": "Process",
            "distance": 0.05,
        }
        rag_cls.return_value.retrieve.return_value = [chunk]
        rag_cls.return_value.get_source_chunks.return_value = [chunk]
        llm_cls.return_value.call_json.return_value = {
            "question": "After structure X is experimentally blocked, which observed result best supports its proposed relationship with function Y?",
            "options": {str(number): f"Choice {number}" for number in range(1, 6)},
            "correct_answer": "1",
            "model_answer": "The excerpt links structure X with function Y.",
        }
        grounding_cls.return_value.score.return_value = 0.82
        grounding_cls.return_value.threshold = 0.55
        grounding_cls.return_value.validate_question.return_value = {
            "grounding_status": "grounded",
            "grounding_score": 0.82,
            "evidence_chunk_id": "bio-lymph",
            "evidence_quote": "Lymphatic capillaries are blind-ended and collect tissue fluid.",
            "reason": "one source-supported answer",
        }
        state = {
            "session_id": "session-1",
            "chroma_collection_id": "session-1",
            "topics": ["Source topic"],
            "num_questions": 1,
            "exam_type": "mcq",
            "difficulty_mode": "adaptive",
            "current_difficulty": 0.8,
            "current_q_index": 0,
            "questions": [],
            "quiz_blueprint": [],
            "flagged_questions": [],
            "agent_logs": [],
        }

        result = quiz_agent(state)

        question = result["questions"][0]
        self.assertEqual(question["source_file"], "biology-notes.pdf")
        self.assertEqual(question["page_number"], 2)
        self.assertEqual(question["grounding_status"], "grounded")
        rag_cls.return_value.retrieve.assert_called()
        grounding_cls.return_value.score.assert_called_once()
        saved = db_cls.return_value.save_question.call_args.args[0]
        self.assertEqual(saved["retrieved_text"], chunk["text"])
        self.assertEqual(saved["grounding_status"], "grounded")

    def test_embedding_grounding_accepts_a_candidate_above_threshold(self):
        grounding = Mock()
        grounding.score.return_value = 0.62
        grounding.threshold = 0.55
        candidate = {
            "question": "Which relationship is supported?",
            "options": {str(number): f"Choice {number}" for number in range(1, 6)},
            "correct_answer": "1",
            "model_answer": "The source supports the first relationship.",
        }
        chunks = [{"chunk_id": "bio-1", "text": "Relevant Biology source text."}]

        audit = _embedding_grounding_audit(grounding, candidate, chunks)

        self.assertEqual(audit["grounding_status"], "grounded")
        self.assertEqual(audit["grounding_score"], 0.62)

    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.GroundingService")
    @patch("app.agents.quiz_agent.RagService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_planned_generation_creates_only_the_current_adaptive_question(
        self, llm_cls, rag_cls, grounding_cls, db_cls
    ):
        chunk = {
            "chunk_id": "bio-lymph",
            "text": (
                "Lymphatic capillaries are blind-ended and collect tissue fluid. "
                "Lymphatic vessels contain valves that maintain flow towards the heart. "
                "Lymph nodes filter lymph and contain many immune cells."
            ),
            "source": "biology.pdf",
            "page": 8,
            "heading": "Lymphatic system",
            "distance": 0.05,
        }
        rag_cls.return_value.get_source_chunks.return_value = [chunk]
        rag_cls.return_value.retrieve.return_value = [chunk]
        grounding_cls.return_value.score.return_value = 0.82
        grounding_cls.return_value.threshold = 0.55

        def mcq(stem, correct, options):
            return {
                "question": stem,
                "options": {str(index): text for index, text in enumerate(options, start=1)},
                "correct_answer": str(correct),
                "model_answer": options[correct - 1],
            }

        lymph_options = [
            "Valves and blind-ended capillaries",
            "No valves and blind-ended capillaries",
            "Valves and open-ended capillaries",
            "No valves and open-ended capillaries",
            "Open ends with outward flow",
        ]
        q1 = mcq(
            "After tissue fluid enters blind-ended lymphatic capillaries, which feature combination best predicts continued one-way movement toward the heart?",
            1,
            lymph_options,
        )
        q2_duplicate = mcq(
            "Which description of lymph capillaries is correct?",
            4,
            [lymph_options[2], lymph_options[4], lymph_options[1], lymph_options[0], lymph_options[3]],
        )
        q3 = mcq(
            "If lymph passes through a node before returning to blood, which result is most directly expected?",
            1,
            ["Filtering lymph", "Pumping blood", "Producing bile", "Digesting proteins", "Ventilating lungs"],
        )
        repaired_q2 = mcq(
            "What maintains one-way lymph flow towards the heart?",
            1,
            ["Vessel valves", "Open capillary ends", "Cardiac muscle", "Alveolar pressure", "Bile salts"],
        )
        llm_cls.return_value.call_json.return_value = {
            "questions": [dict(q1, plan_index=1)]
        }
        state = {
            "session_id": "batch-session",
            "chroma_collection_id": "batch-session",
            "topics": ["Lymphatic system"],
            "num_questions": 3,
            "exam_type": "mcq",
            "difficulty_mode": "adaptive",
            "current_difficulty": 0.8,
            "current_q_index": 0,
            "questions": [],
            "quiz_blueprint": [],
            "flagged_questions": [],
            "agent_logs": [],
        }

        result = quiz_agent(state)

        self.assertEqual(len(result["questions"]), 1)
        self.assertEqual(result["questions"][0]["difficulty"], 0.8)
        self.assertEqual(len(result["quiz_blueprint"]), 3)

        # Retrying the current question must not pre-generate the next one at
        # the previous difficulty.
        retry_state = dict(state)
        retry_state.update(result)
        retry_state["current_q_index"] = 0
        retry_result = quiz_agent(retry_state)
        self.assertEqual(len(retry_result["questions"]), 1)
        self.assertEqual(llm_cls.return_value.call_json.call_count, 1)

        llm_cls.return_value.call_json.return_value = {
            "questions": [dict(q3, plan_index=1)]
        }
        next_state = dict(state)
        next_state.update(result)
        next_state["current_q_index"] = 1
        next_state["current_difficulty"] = 0.5

        next_result = quiz_agent(next_state)

        self.assertEqual(len(next_result["questions"]), 2)
        self.assertEqual(next_result["questions"][1]["difficulty"], 0.5)
        self.assertEqual(db_cls.return_value.save_question.call_count, 2)
        self.assertEqual(
            llm_cls.return_value.call_json.call_args_list[0].kwargs["max_new_tokens"],
            384,
        )

class TopicOnlyAdaptiveTests(unittest.TestCase):
    @patch("app.agents.quiz_agent.DbService")
    @patch("app.agents.quiz_agent.LlmService")
    def test_topic_only_question_uses_model_and_current_adaptive_difficulty(self, llm_cls, db_cls):
        llm_cls.return_value.check_health.return_value = True
        llm_cls.return_value.call_json.return_value = {
            "question": "Which outcome best explains reduced ATP production after the inner mitochondrial membrane loses its proton gradient?",
            "options": {
                "1": "ATP synthase receives less proton-motive force",
                "2": "DNA replication immediately doubles",
                "3": "Ribosomes stop peptide bond formation",
                "4": "Lysosomes increase extracellular digestion",
                "5": "Golgi cisternae generate oxygen directly",
            },
            "correct_answer": "1",
            "model_answer": "The proton gradient supplies the proton-motive force used by ATP synthase. Its loss therefore reduces oxidative phosphorylation even when other mitochondrial structures remain present.",
        }
        state = {
            "session_id": "topic-session",
            "student_id": "student",
            "document_ids": [],
            "requested_topic": "Cellular respiration",
            "questions": [],
            "current_q_index": 0,
            "num_questions": 5,
            "exam_type": "mcq",
            "difficulty_mode": "adaptive",
            "current_difficulty": 0.5,
            "agent_logs": [],
            "flagged_questions": [],
            "quiz_blueprint": [],
        }

        result = quiz_agent(state)

        self.assertEqual(result["questions"][0]["difficulty"], 0.8)
        self.assertEqual(result["questions"][0]["grounding_status"], "topic_model")
        self.assertIn("Difficulty: hard (0.80/1.0)", llm_cls.return_value.call_json.call_args.args[0])
        db_cls.return_value.save_question.assert_called_once()


if __name__ == "__main__":
    unittest.main()
