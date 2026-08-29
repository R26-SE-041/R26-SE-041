import unittest
from unittest.mock import Mock

from app.services.hint_pipeline import (
    SAFE_FALLBACKS,
    _has_correct_answer_term_overlap,
    _is_question_relevant,
    _progression_similarity,
    _select_relevant_biology_chunks,
    _uses_forbidden_language,
    _validate_hint,
    generate_adaptive_hint,
)


BIOLOGY_QUESTION = {
    "q_id": "bio-1",
    "q_type": "mcq",
    "question": "Which polysaccharide provides the main structural framework of a plant cell wall?",
    "topic": "Plant cell structure",
    "correct_answer": "1",
    "options": {
        "1": "Cellulose",
        "2": "Glycogen",
        "3": "Starch",
        "4": "Chitin",
        "5": "Peptidoglycan",
    },
    "model_answer": "Cellulose forms strong microfibrils that provide tensile strength to the plant cell wall.",
}


class HintValidationTests(unittest.TestCase):
    def test_detects_correct_answer_term_overlap(self):
        self.assertTrue(
            _has_correct_answer_term_overlap(
                "Think about how cellulose microfibrils resist stretching.",
                BIOLOGY_QUESTION,
            )
        )

    def test_rejects_option_numbers_and_direct_elimination_language(self):
        reasons = _validate_hint(
            "Remove option 2, then focus on plant cell wall organization and structural support.",
            BIOLOGY_QUESTION,
            0,
            [],
        )
        self.assertIn("option_number", reasons)
        self.assertIn("direct_elimination_language", reasons)

    def test_progression_similarity_detects_reworded_repetition(self):
        hard = "Connect plant cell wall organization with the mechanical support required during growth."
        repeated = "Connect mechanical support during plant growth with the organization of the cell wall."
        self.assertGreaterEqual(_progression_similarity(repeated, [hard]), 0.72)

    def test_question_type_relevance_rejects_unrelated_hint(self):
        self.assertFalse(
            _is_question_relevant(
                "Consider how a financial ledger records liabilities across an accounting period.",
                BIOLOGY_QUESTION,
            )
        )

    def test_rag_keeps_only_sufficiently_relevant_biology_chunks(self):
        chunks = [
            {
                "text": "Plant cell walls contain structural polysaccharides arranged around the cell membrane.",
                "distance": 0.20,
            },
            {
                "text": "Corporate tax liabilities are reconciled at the end of the accounting year.",
                "distance": 0.72,
            },
        ]
        selected = _select_relevant_biology_chunks(chunks, BIOLOGY_QUESTION)
        self.assertEqual(len(selected), 1)
        self.assertIn("Plant cell walls", selected[0]["text"])

    def test_safe_fallbacks_never_use_direct_elimination_language(self):
        for hint in SAFE_FALLBACKS:
            self.assertFalse(_uses_forbidden_language(hint))
            self.assertNotRegex(hint, r"\b[1-5]\b")


class AdaptiveHintGenerationTests(unittest.TestCase):
    def test_retries_failed_safety_candidate_then_accepts_safe_hint(self):
        llm = Mock()
        llm.call.side_effect = [
            "Choose option 1 because cellulose is the structural material.",
            (
                "Relate the source's organized structural polysaccharides to the strength described for the cell wall. "
                "Focus on the relationship between organization and support."
            ),
        ]
        rag = Mock()
        rag.retrieve.return_value = [
            {
                "text": "Plant cell walls gain strength from organized structural polysaccharides.",
                "distance": 0.18,
            }
        ]

        hint = generate_adaptive_hint(llm, rag, BIOLOGY_QUESTION, 0, "collection")

        self.assertEqual(llm.call.call_count, 2)
        self.assertNotIn("option", hint.casefold())
        self.assertNotIn("cellulose", hint.casefold())

    def test_medium_prompt_receives_hard_history_and_requires_progression(self):
        hard = "Connect plant cell wall organization with the mechanical support required during growth."
        medium = (
            "Trace how the arrangement of structural polymers distributes tension across a growing plant cell. "
            "Use that structure-to-function step when comparing the described wall materials."
        )
        llm = Mock()
        llm.call.return_value = medium
        rag = Mock()
        rag.retrieve.return_value = [{
            "text": "Structural polymers are arranged across the growing plant cell wall to distribute tension.",
            "distance": 0.18,
        }]
        hint = generate_adaptive_hint(
            llm,
            rag,
            BIOLOGY_QUESTION,
            1,
            "collection",
            previous_hints=[hard],
        )

        self.assertEqual(hint, medium)
        self.assertIn(hard, llm.call.call_args.args[0])

    def test_weak_rag_context_is_not_injected(self):
        llm = Mock()
        llm.call.return_value = (
            "Relate plant cell wall organization to the mechanical demands placed on a growing cell. "
            "Focus on the molecular arrangement needed for sustained structural support."
        )
        rag = Mock()
        rag.retrieve.return_value = [
            {"text": "UNRELATED_ACCOUNTING_CONTEXT", "distance": 0.81}
        ]

        hint = generate_adaptive_hint(llm, rag, BIOLOGY_QUESTION, 0, "collection")

        self.assertEqual(
            hint,
            "Relate plant cell wall organization to the mechanical demands placed on a growing cell. "
            "Focus on the molecular arrangement needed for sustained structural support.",
        )
        llm.call.assert_called_once()
        self.assertNotIn("UNRELATED_ACCOUNTING_CONTEXT", llm.call.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
