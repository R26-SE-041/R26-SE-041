import unittest
from unittest.mock import Mock, patch

from app.services.grounding_service import GroundingService


class GroundingAuditTests(unittest.TestCase):
    @patch.object(GroundingService, "score", return_value=0.8)
    def test_requires_an_exact_quote_from_the_named_pdf_chunk(self, _score):
        service = GroundingService()
        llm = Mock()
        llm.call_json.return_value = {
            "is_biology": True,
            "question_supported": True,
            "correct_answer_supported": True,
            "explanation_supported": True,
            "exactly_one_correct": True,
            "distractors_contextual": True,
            "has_unsupported_claims": False,
            "evidence_chunk_id": "p3",
            "evidence_quote": "membrane controls movement of substances",
            "reason": "directly stated",
        }
        question = {
            "question": "Which function is stated?",
            "options": {str(i): f"Choice {i}" for i in range(1, 6)},
            "correct_answer": "1",
            "model_answer": "The stated function is supported.",
        }
        chunks = [{
            "chunk_id": "p3",
            "source": "notes.pdf",
            "page": 3,
            "text": "The cell membrane controls movement of substances across its boundary.",
        }]

        result = service.validate_question(llm, question, chunks)

        self.assertEqual(result["grounding_status"], "grounded")

    @patch.object(GroundingService, "score", return_value=0.8)
    def test_rejects_a_claim_when_the_evidence_quote_was_invented(self, _score):
        service = GroundingService()
        llm = Mock()
        llm.call_json.return_value = {
            "is_biology": True,
            "question_supported": True,
            "correct_answer_supported": True,
            "explanation_supported": True,
            "exactly_one_correct": True,
            "distractors_contextual": True,
            "has_unsupported_claims": False,
            "evidence_chunk_id": "p3",
            "evidence_quote": "an invented biological mechanism",
            "reason": "claimed support",
        }
        question = {
            "question": "Which function is stated?",
            "options": {str(i): f"Choice {i}" for i in range(1, 6)},
            "correct_answer": "1",
            "model_answer": "Explanation.",
        }
        chunks = [{"chunk_id": "p3", "source": "notes.pdf", "page": 3, "text": "Different source text only."}]

        result = service.validate_question(llm, question, chunks)

        self.assertEqual(result["grounding_status"], "rejected")

    @patch.object(GroundingService, "score", return_value=0.8)
    def test_rejects_when_the_grounding_audit_is_unavailable(self, _score):
        service = GroundingService()
        llm = Mock()
        llm.call_json.side_effect = RuntimeError("temporary model failure")
        question = {
            "question": "Which function is stated?",
            "options": {str(i): f"Choice {i}" for i in range(1, 6)},
            "correct_answer": "1",
            "model_answer": "Explanation.",
        }
        chunks = [{
            "chunk_id": "p3",
            "source": "notes.pdf",
            "page": 3,
            "text": "The cell membrane controls movement of substances across its boundary.",
        }]

        result = service.validate_question(llm, question, chunks)

        self.assertEqual(result["grounding_status"], "rejected")
        self.assertEqual(result["reason"], "grounding_audit_unavailable")


if __name__ == "__main__":
    unittest.main()
