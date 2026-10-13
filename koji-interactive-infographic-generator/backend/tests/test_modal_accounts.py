"""Routing switches must be atomic, checked and independent of queued jobs."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from studio import modal_accounts as routing


def endpoints(name):
    return {service: f"https://{name}--{service}.modal.run" for service in routing.ENDPOINT_KEYS}


class ModalAccountTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.registry = self.root / "modal-accounts.json"
        self.state = self.root / "modal-active.json"
        self.config = {"version": 1, "accounts": {
            name: {"profile": name, "environment": "main", "endpoints": endpoints(name)}
            for name in ("first", "second", "third")
        }}
        self.registry.write_text(json.dumps(self.config), encoding="utf-8")
        env = patch.dict(os.environ, {
            "KOJI_MODAL_ACCOUNTS_FILE": str(self.registry), "KOJI_MODAL_STATE_FILE": str(self.state),
            "PROMPT_AGENT_URL": "http://localhost:1234", "ORCHESTRATOR_URL": "http://localhost:5678",
        })
        env.start()
        self.addCleanup(env.stop)
        health = patch.object(routing.requests, "get", return_value=Mock(json=lambda: {"status": "ok"}))
        self.get = health.start()
        self.addCleanup(health.stop)

    def test_environment_routing_until_first_activation(self):
        self.assertEqual(routing.routing_endpoints()["prompt"], "http://localhost:1234")
        self.assertFalse(self.state.exists())

    def test_switch_reads_fresh_routing_and_preserves_old_job_snapshot(self):
        routing.activate("first", 1)
        old_job = {"endpoints": routing.routing_endpoints()}
        routing.activate("second", 1)
        self.assertEqual(old_job["endpoints"], endpoints("first"))
        self.assertEqual(routing.routing_endpoints(), endpoints("second"))
        self.assertEqual(routing.current_state()["previous"]["account"], "first")
        self.assertEqual(self.get.call_count, 14)

    def test_failed_health_leaves_previous_bytes_unchanged(self):
        routing.activate("first", 1)
        before = self.state.read_bytes()
        self.get.side_effect = requests.ConnectionError("unavailable")
        with self.assertRaisesRegex(ValueError, "Health checks failed"):
            routing.activate("second", 1)
        self.assertEqual(self.state.read_bytes(), before)

    def test_bad_health_payload_blocks_activation(self):
        for body in ({"status": "error"}, {}, [], "ok"):
            with self.subTest(body=body):
                self.get.return_value = Mock(json=lambda: body)
                with self.assertRaisesRegex(ValueError, "Health checks failed"):
                    routing.activate("first", 1)
                self.assertFalse(self.state.exists())

    def test_rollback_restores_previous_account(self):
        routing.activate("first", 1)
        routing.activate("second", 1)
        routing.activate(None, 1, rollback=True)
        self.assertEqual(routing.routing_endpoints(), endpoints("first"))

    def test_first_switch_can_rollback_to_environment(self):
        routing.activate("first", 1)
        routing.activate(None, 1, rollback=True)
        self.assertEqual(routing.routing_endpoints()["prompt"], "http://localhost:1234")

    def test_failed_rollback_does_not_change_active_account(self):
        routing.activate("first", 1)
        routing.activate("second", 1)
        self.get.side_effect = requests.Timeout()
        with self.assertRaises(ValueError):
            routing.activate(None, 1, rollback=True)
        self.assertEqual(routing.routing_endpoints(), endpoints("second"))

    def test_registry_edits_do_not_mutate_active_snapshot(self):
        routing.activate("first", 1)
        self.config["accounts"]["first"]["endpoints"] = endpoints("replacement")
        self.registry.write_text(json.dumps(self.config))
        self.assertEqual(routing.routing_endpoints(), endpoints("first"))
        routing.activate("first", 1)
        self.assertEqual(routing.routing_endpoints(), endpoints("replacement"))

    def test_unknown_or_incomplete_account_never_changes_routing(self):
        with self.assertRaisesRegex(ValueError, "Unknown account"):
            routing.activate("unknown", 1)
        del self.config["accounts"]["first"]["endpoints"]["image"]
        self.registry.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, "all six"):
            routing.activate("first", 1)
        self.get.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_unsafe_origins_are_rejected(self):
        for url in ("http://example.com", "https://u:p@example.com", "https://example.com/path",
                    "https://example.com?token=x", "https://example.com#fragment", "https://example.com:8000"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                routing.validate_endpoints({**endpoints("first"), "prompt": url})

    def test_corrupted_active_state_fails_closed(self):
        self.state.write_text('{"version":1,"active":{"account":"first","endpoints":{}}}')
        with self.assertRaises(ValueError):
            routing.routing_endpoints()
        self.state.write_text("invalid json")
        with self.assertRaises(ValueError):
            routing.routing_endpoints()

    def test_replace_failure_preserves_state_and_cleans_temporary_file(self):
        routing.activate("first", 1)
        before = self.state.read_bytes()
        with patch.object(routing.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                routing.activate("second", 1)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.tmp")), [])
        # Failed operations release the operator lock.
        routing.activate("third", 1)
        self.assertEqual(routing.current_state()["active"]["account"], "third")

    def test_cli_invalid_account_returns_failure(self):
        self.assertEqual(routing.main(["check", "unknown"]), 1)

    def test_concurrent_switch_is_rejected_before_health_checks(self):
        with routing.switch_lock():
            with self.assertRaisesRegex(ValueError, "Another account switch"):
                routing.activate("first", 1)
        self.get.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_no_previous_configuration_cannot_rollback(self):
        with self.assertRaisesRegex(ValueError, "No previous"):
            routing.activate(None, 1, rollback=True)

    def test_api_proxy_and_job_submission_follow_switch_without_restart(self):
        from fastapi.testclient import TestClient
        from studio.main import app, require_user
        from uuid import uuid4

        self.get.return_value = Mock(status_code=200, json=lambda: {"status": "ok"})
        app.dependency_overrides[require_user] = lambda: str(uuid4())
        self.addCleanup(app.dependency_overrides.clear)
        client = TestClient(app)
        with patch("studio.main.repo") as repo:
            repo.create_job.return_value = {"id": str(uuid4()), "kind": "enhance", "status": "queued",
                                           "stage": "queued", "error": None, "result": None}
            for name in ("first", "second"):
                routing.activate(name, 1)
                self.assertEqual(client.get("/agents/prompt/health").status_code, 200)
                self.assertEqual(self.get.call_args.args[0], endpoints(name)["prompt"] + "/health")
                response = client.post("/studio/jobs", json={"request_id": str(uuid4()), "kind": "enhance",
                                                            "prompt": "Human heart", "mode": "general"})
                self.assertEqual(response.status_code, 202, response.text)
                self.assertEqual(repo.create_job.call_args.args[2], {
                    service: url for service, url in endpoints(name).items() if service != "orchestrator"
                })

    def test_legacy_memory_proxy_uses_selected_orchestrator(self):
        from fastapi.testclient import TestClient
        from studio.main import app

        routing.activate("second", 1)
        with patch("studio.main.requests.request", return_value=Mock(status_code=200, json=lambda: {})) as request:
            response = TestClient(app).get("/memory/context")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.call_args.args[1], endpoints("second")["orchestrator"] + "/memory/context")

    def test_agent_proxy_requires_login(self):
        from fastapi.testclient import TestClient
        from studio.main import app

        self.assertEqual(TestClient(app).get("/agents/prompt/health").status_code, 401)
        self.get.assert_not_called()

    def test_deployment_uses_explicit_profile_without_shell_token_override(self):
        path = Path(__file__).resolve().parents[2] / "deploy/modal/deploy_accounts.py"
        spec = importlib.util.spec_from_file_location("deploy_modal_accounts", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.dict(os.environ, {"MODAL_TOKEN_ID": "wrong", "MODAL_TOKEN_SECRET": "wrong"}), \
                patch.object(module.subprocess, "run") as run:
            module.deploy("first", self.config["accounts"]["first"], include_orchestrator=True)
        for call in run.call_args_list:
            environment = call.kwargs["env"]
            self.assertEqual(environment["MODAL_PROFILE"], "first")
            self.assertEqual(environment["MODAL_ENVIRONMENT"], "main")
            self.assertNotIn("MODAL_TOKEN_ID", environment)
            self.assertNotIn("MODAL_TOKEN_SECRET", environment)
        self.assertEqual(run.call_count, 9)
        secret_command = run.call_args_list[-2].args[0]
        self.assertIn("PROMPT_AGENT_URL=" + endpoints("first")["prompt"], secret_command)


if __name__ == "__main__":
    unittest.main()
