import unittest
from unittest.mock import Mock, patch

import app.graph.graph  # noqa: F401
from app.agents.recommendation_agent import _generate_concept_notes, recommendation_agent


class RecallNotesTests(unittest.TestCase):
    @patch("app.agents.recommendation_agent.build_resources")
    @patch("app.agents.recommendation_agent.LlmService")
    def test_fast_snapshot_uses_no_model_or_live_web(self, llm_cls, resources):
        state = {
            "session_id": "fast",
            "subject": "Biology",
            "chroma_collection_id": "fast",
            "topic_scores": {"Transport": {"correct": 0, "total": 1}},
            "questions": [{
                "q_id": "q1", "topic": "Transport",
                "model_answer": (
                    "Membranes regulate movement between compartments through selective biological mechanisms. "
                    "Concentration relationships influence the direction and net rate of that movement."
                ),
                "source_chunks": [], "source_file": "biology.pdf", "page_number": 1,
            }],
            "answers": [{"q_id": "q1", "attempts": 4, "is_correct": False}],
            "agent_logs": [],
        }

        result = recommendation_agent(state, fast=True)

        self.assertTrue(result["recommendations"][0]["concept_notes"])
        llm_cls.return_value.call.assert_not_called()
        resources.assert_not_called()

    @patch("app.agents.recommendation_agent.build_resources")
    @patch("app.agents.recommendation_agent.RagService")
    @patch("app.agents.recommendation_agent.LlmService")
    def test_perfect_score_gets_enrichment_not_false_weak_area(self, llm_cls, rag_cls, resources):
        llm_cls.return_value.call.return_value = "- **Extension**: A supported explanation that deepens recall using the source relationship."
        resources.return_value = [{
            "label": "English", "title": "Exact video", "url": "https://www.youtube.com/watch?v=abcdefghijk", "source": "YouTube",
        }]
        state = {
            "session_id": "perfect",
            "subject": "Biology",
            "chroma_collection_id": "perfect",
            "topic_scores": {"Golgi apparatus": {"correct": 1, "total": 1}},
            "questions": [{
                "q_id": "q1", "topic": "Golgi apparatus", "model_answer": "Golgi cisternae modify and package materials.",
                "source_chunks": [], "source_file": "biology.pdf", "page_number": 1,
            }],
            "answers": [{"q_id": "q1", "attempts": 1, "is_correct": True}],
            "agent_logs": [],
        }
        result = recommendation_agent(state)
        self.assertEqual(result["weak_topics"], [])
        self.assertEqual(result["recommendations"][0]["recommendation_type"], "enrichment")
        self.assertEqual(result["recommendations"][0]["resources"][0]["source"], "YouTube")

    def test_uses_question_source_chunks_and_requests_deep_notes(self):
        rag = Mock()
        llm = Mock()
        llm.call.return_value = "\n".join(
            f"- **Point {index}**: This is a supported multi-sentence recall explanation. It connects the relevant structure and process."
            for index in range(1, 8)
        )
        chunks = [{"text": "Golgi cisternae modify and package cellular materials."}]

        notes = _generate_concept_notes(
            "Golgi apparatus", rag, llm, "collection", source_chunks=chunks
        )

        self.assertEqual(len(notes), 7)
        rag.retrieve.assert_not_called()
        self.assertEqual(llm.call.call_args.kwargs["max_new_tokens"], 700)
        self.assertIn("G.C.E. A/L Biology", llm.call.call_args.args[0])

    def test_returns_no_generic_knowledge_when_source_context_is_absent(self):
        rag = Mock()
        rag.retrieve.return_value = []
        llm = Mock()

        notes = _generate_concept_notes("Unknown topic", rag, llm, "collection")

        self.assertEqual(notes, [])
        llm.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
