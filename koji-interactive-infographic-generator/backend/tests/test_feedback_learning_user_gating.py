import unittest
from unittest.mock import patch

from shared import feedback_learning


def _row(agent_name: str, reason_code: str, distinct_users: int, distinct_sessions: int = 5) -> dict:
    return {
        "agent_name": agent_name,
        "reason_code": reason_code,
        "evidence_count": 12,
        "distinct_sessions": distinct_sessions,
        "distinct_users": distinct_users,
        "pair_ids": ["pair-1", "pair-2"],
        "positive_reasons": [],
    }


class ConsolidateFeedbackCandidatesUserGatingTests(unittest.TestCase):
    @patch("shared.rag.embed", return_value=[0.0] * 384)
    @patch("shared.db.upsert_agent_memory", return_value="mem-id")
    @patch("shared.db.upsert_memory_candidate", return_value="cand-id")
    @patch("shared.db.list_preference_reason_aggregates")
    def test_minimum_users_is_forwarded_to_the_aggregate_query(
        self, list_aggregates, upsert_candidate, upsert_memory, embed
    ) -> None:
        list_aggregates.return_value = []

        feedback_learning.consolidate_feedback_candidates(
            memento_min_pairs=10, minimum_sessions=3, minimum_users=5
        )

        list_aggregates.assert_called_once_with(10, 3, 5)

    @patch("shared.rag.embed", return_value=[0.0] * 384)
    @patch("shared.db.upsert_agent_memory", return_value="mem-id")
    @patch("shared.db.upsert_memory_candidate", return_value="cand-id")
    @patch("shared.db.list_preference_reason_aggregates")
    def test_distinct_users_is_recorded_on_the_candidate(
        self, list_aggregates, upsert_candidate, upsert_memory, embed
    ) -> None:
        list_aggregates.return_value = [_row("prompt-agent", "meaning_changed", distinct_users=4)]

        candidates = feedback_learning.consolidate_feedback_candidates()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["distinct_users"], 4)
        stored = upsert_candidate.call_args.args[0]
        self.assertEqual(stored["distinct_users"], 4)

    @patch("shared.rag.embed", return_value=[0.0] * 384)
    @patch("shared.db.upsert_agent_memory", return_value="mem-id")
    @patch("shared.db.upsert_memory_candidate", return_value="cand-id")
    @patch("shared.db.list_preference_reason_aggregates")
    def test_cross_agent_global_candidate_takes_the_weakest_user_corroboration(
        self, list_aggregates, upsert_candidate, upsert_memory, embed
    ) -> None:
        # Same reason code from three different agents, so it also qualifies
        # for the existing >=3-agents global-promotion rule.
        list_aggregates.return_value = [
            _row("prompt-agent", "meaning_changed", distinct_users=3),
            _row("image-agent", "wrong_content", distinct_users=3),
            _row("interactive-agent", "wrong_region", distinct_users=8),
        ]
        with patch.dict(
            feedback_learning.LESSONS,
            {
                "prompt-agent": {"meaning_changed": "lesson-a"},
                "image-agent": {"wrong_content": "lesson-b"},
                "interactive-agent": {"wrong_region": "lesson-c"},
            },
        ):
            candidates = feedback_learning.consolidate_feedback_candidates()

        global_candidates = [c for c in candidates if c["scope"] == "global"]
        self.assertEqual(len(global_candidates), 0)  # different reason codes never merge

        # Re-run with a shared reason code across the three agents to hit the global path.
        list_aggregates.return_value = [
            {**_row("prompt-agent", "shared_reason", distinct_users=3)},
            {**_row("image-agent", "shared_reason", distinct_users=6)},
            {**_row("interactive-agent", "shared_reason", distinct_users=9)},
        ]
        with patch.dict(
            feedback_learning.LESSONS,
            {
                "prompt-agent": {"shared_reason": "lesson-a"},
                "image-agent": {"shared_reason": "lesson-b"},
                "interactive-agent": {"shared_reason": "lesson-c"},
            },
        ):
            candidates = feedback_learning.consolidate_feedback_candidates()

        global_candidates = [c for c in candidates if c["scope"] == "global"]
        self.assertEqual(len(global_candidates), 1)
        self.assertEqual(global_candidates[0]["distinct_users"], 9)


if __name__ == "__main__":
    unittest.main()
