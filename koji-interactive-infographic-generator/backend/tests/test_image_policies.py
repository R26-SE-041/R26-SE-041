from __future__ import annotations

import unittest

from shared.image_policies import POLICY_VERSION, select_image_policy


class ImagePolicyTests(unittest.TestCase):
    def test_policy_has_a_runtime_version(self) -> None:
        self.assertEqual(POLICY_VERSION, "image-runtime-v2")

    def test_generic_policy_preserves_plain_prompt(self) -> None:
        policy = select_image_policy("generic")
        self.assertEqual(policy.policy_id, "generic-preserve-intent-v1")
        self.assertEqual(policy.apply("cat on a beach"), "cat on a beach")
        self.assertNotIn("ANATOMY", policy.apply("cat on a beach"))

    def test_anatomy_policy_keeps_constraints_after_untrusted_context(self) -> None:
        policy = select_image_policy("anatomy")
        prompt = policy.apply(
            "validated heart prompt",
            memory_context="use a dark scene with labels",
            feedback="add arrows",
        )
        self.assertEqual(policy.policy_id, "anatomy-clean-base-v1")
        self.assertTrue(prompt.endswith("notes or recalled preferences."))
        self.assertIn("white or very light neutral background", prompt)
        self.assertIn("do not render text, labels", prompt)

    def test_domain_rules_can_be_disabled_for_ablation(self) -> None:
        prompt = select_image_policy("anatomy").apply(
            "heart",
            apply_domain_rules=False,
        )
        self.assertNotIn("FINAL ANATOMY OUTPUT RULES", prompt)

    def test_optional_context_is_bounded_and_cleaned(self) -> None:
        prompt = select_image_policy("generic").apply(
            "cell",
            memory_context="blue\x00 " + ("x" * 3_000),
        )
        context = prompt.split("Validated relevant generation preferences: ", 1)[1]
        self.assertNotIn("\x00", context)
        self.assertLessEqual(len(context), 2_000)


if __name__ == "__main__":
    unittest.main()
