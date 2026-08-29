import unittest

import app.graph.graph  # noqa: F401
from app.agents.adaptive_agent import adaptive_agent


class AttemptDifficultyTests(unittest.TestCase):
    def _state(self, attempts: int, mode: str = "adaptive") -> dict:
        return {
            "session_id": "adaptive-session",
            "answers": [{"attempts": attempts, "is_correct": attempts < 4}],
            "current_difficulty": 0.8,
            "difficulty_mode": mode,
            "agent_logs": [],
        }

    def test_attempts_one_and_two_keep_next_question_hard(self):
        self.assertEqual(adaptive_agent(self._state(1))["current_difficulty"], 0.8)
        self.assertEqual(adaptive_agent(self._state(2))["current_difficulty"], 0.8)

    def test_attempt_three_makes_next_question_medium(self):
        self.assertEqual(adaptive_agent(self._state(3))["current_difficulty"], 0.5)

    def test_attempt_four_makes_next_question_easy(self):
        self.assertEqual(adaptive_agent(self._state(4))["current_difficulty"], 0.2)

    def test_fixed_difficulty_mode_is_not_overwritten(self):
        result = adaptive_agent(self._state(4, mode="medium"))
        self.assertNotIn("current_difficulty", result)


if __name__ == "__main__":
    unittest.main()
