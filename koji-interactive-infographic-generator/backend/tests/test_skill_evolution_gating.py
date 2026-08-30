import unittest
from unittest.mock import patch

from shared import skill_evolution


VALIDATION_OK = {
    "old_score": 6.0,
    "new_score": 8.0,
    "pairs": [{"prompt": "p", "old_score": 6.0, "new_score": 8.0}],
    "errors": [],
}

VALIDATION_NO_IMPROVEMENT = {
    "old_score": 7.0,
    "new_score": 7.05,
    "pairs": [{"prompt": "p", "old_score": 7.0, "new_score": 7.05}],
    "errors": [],
}


class RunAutomaticEvolutionGatingTests(unittest.TestCase):
    """A candidate that clears the improvement bar must be recorded and left
    pending review, never deployed automatically."""

    @patch("shared.db.record_skill_version", return_value="row-id")
    @patch("shared.db.get_latest_skill_version_number", return_value=3)
    @patch("shared.db.list_active_feedback_patterns", return_value=[{"id": "pat-1"}])
    @patch("shared.db.list_validation_prompts", return_value=["a heart", "a cell"])
    @patch("shared.db.list_high_scoring_experiences", return_value=[{"raw_prompt": "x"}] * 50)
    @patch("shared.feedback_patterns.analyze_and_store")
    @patch.object(skill_evolution, "validate_rules", return_value=VALIDATION_OK)
    @patch.object(skill_evolution, "generate_candidate", return_value="# SKILL.md candidate")
    @patch.object(skill_evolution, "deploy_rules")
    @patch("shared.db.activate_skill_version")
    @patch("shared.db.mark_feedback_patterns_consumed")
    def test_improving_candidate_is_not_auto_deployed(
        self,
        mark_consumed,
        activate,
        deploy_rules,
        generate_candidate,
        validate_rules,
        analyze_and_store,
        list_experiences,
        list_prompts,
        list_patterns,
        latest_version,
        record_version,
    ) -> None:
        result = skill_evolution.run_automatic_evolution(
            skill_directory=__import__("pathlib").Path("/tmp/does-not-matter"),
            minimum_experiences=50,
            validation_prompt_count=2,
        )

        self.assertEqual(result["status"], "pending_review")
        record_version.assert_called_once()
        self.assertEqual(record_version.call_args.kwargs["status"], "candidate")
        deploy_rules.assert_not_called()
        activate.assert_not_called()
        mark_consumed.assert_not_called()

    @patch("shared.db.record_skill_version", return_value="row-id")
    @patch("shared.db.get_latest_skill_version_number", return_value=3)
    @patch("shared.db.list_active_feedback_patterns", return_value=[])
    @patch("shared.db.list_validation_prompts", return_value=["a heart", "a cell"])
    @patch("shared.db.list_high_scoring_experiences", return_value=[{"raw_prompt": "x"}] * 50)
    @patch("shared.feedback_patterns.analyze_and_store")
    @patch.object(skill_evolution, "validate_rules", return_value=VALIDATION_NO_IMPROVEMENT)
    @patch.object(skill_evolution, "generate_candidate", return_value="# SKILL.md candidate")
    def test_candidate_below_improvement_bar_is_rejected(
        self,
        generate_candidate,
        validate_rules,
        analyze_and_store,
        list_experiences,
        list_prompts,
        list_patterns,
        latest_version,
        record_version,
    ) -> None:
        result = skill_evolution.run_automatic_evolution(
            skill_directory=__import__("pathlib").Path("/tmp/does-not-matter"),
            minimum_experiences=50,
            validation_prompt_count=2,
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(record_version.call_args.kwargs["status"], "rejected")


class ApproveAndDeploySkillVersionTests(unittest.TestCase):
    @patch("shared.db.mark_feedback_patterns_consumed")
    @patch("shared.db.activate_skill_version")
    @patch.object(skill_evolution, "deploy_rules")
    @patch(
        "shared.db.get_skill_version",
        return_value={"version": 4, "content": "# SKILL.md", "status": "candidate", "feedback_pattern_ids": ["pat-1"]},
    )
    def test_deploys_a_pending_candidate(self, get_version, deploy_rules, activate, mark_consumed) -> None:
        callback_calls = []
        result = skill_evolution.approve_and_deploy_skill_version(
            skill_directory=__import__("pathlib").Path("/tmp/does-not-matter"),
            version=4,
            deployment_callback=lambda: callback_calls.append(True),
        )

        self.assertEqual(result, {"status": "deployed", "version": 4})
        deploy_rules.assert_called_once()
        activate.assert_called_once_with(4)
        mark_consumed.assert_called_once_with(["pat-1"])
        self.assertEqual(callback_calls, [True])

    @patch("shared.db.get_skill_version", return_value=None)
    def test_raises_for_unknown_version(self, get_version) -> None:
        with self.assertRaises(ValueError):
            skill_evolution.approve_and_deploy_skill_version(
                skill_directory=__import__("pathlib").Path("/tmp/does-not-matter"), version=99
            )

    @patch("shared.db.get_skill_version", return_value={"version": 4, "content": "x", "status": "deployed"})
    def test_raises_when_version_is_not_a_pending_candidate(self, get_version) -> None:
        with self.assertRaises(ValueError):
            skill_evolution.approve_and_deploy_skill_version(
                skill_directory=__import__("pathlib").Path("/tmp/does-not-matter"), version=4
            )


if __name__ == "__main__":
    unittest.main()
