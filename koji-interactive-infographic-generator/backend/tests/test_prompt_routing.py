from __future__ import annotations

import unittest

from shared.prompt_routing import deterministic_route, route_from_model


class PromptRoutingTests(unittest.TestCase):
    def test_human_organs_route_to_anatomy(self) -> None:
        for prompt in (
            "posterior cross section of pancreas",
            "human eye anatomy",
            "eye",
            "retina cross section",
            "skull posterior view",
            "hand",
            "femur",
            "optic nerve",
            "show the mitral valve",
            "spleen for a medical student",
        ):
            with self.subTest(prompt=prompt):
                decision = deterministic_route(prompt)
                self.assertIsNotNone(decision)
                self.assertEqual(decision.route, "anatomy")

    def test_normal_visuals_route_to_generic(self) -> None:
        for prompt in (
            "yellow flower", "cute orange cat", "cross section of a car engine",
            "cat with bright blue eyes", "pig liver", "horse heart anatomy",
            "hand-drawn flower poster",
        ):
            with self.subTest(prompt=prompt):
                decision = deterministic_route(prompt)
                self.assertIsNotNone(decision)
                self.assertEqual(decision.route, "generic")

    def test_metaphorical_organ_term_is_generic(self) -> None:
        decision = deterministic_route("a heart-shaped flower logo")
        self.assertEqual(decision.route, "generic")
        self.assertEqual(decision.reason_code, "metaphorical_organ_term")

    def test_ambiguous_prompt_is_deferred_to_qwen(self) -> None:
        self.assertIsNone(deterministic_route("an intricate internal structure"))

    def test_qwen_contract_is_validated(self) -> None:
        decision = route_from_model({
            "route": "anatomy",
            "confidence": 0.91,
            "reason_code": "human_organ_request",
            "subject": "pancreas",
        })
        self.assertEqual(decision.route, "anatomy")
        self.assertEqual(decision.subject, "pancreas")
        self.assertIsNone(route_from_model({"route": "invalid", "confidence": 1}))


if __name__ == "__main__":
    unittest.main()
