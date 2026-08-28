from __future__ import annotations

import unittest

from shared.image_policies import select_image_policy


class ImagePolicyTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
