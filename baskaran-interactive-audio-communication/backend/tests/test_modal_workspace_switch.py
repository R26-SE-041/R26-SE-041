"""Switching must preserve unrelated configuration and reject unverified targets."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "modal_workspaces.py"
spec = importlib.util.spec_from_file_location("modal_workspaces", MODULE)
workspaces = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspaces)


class SwitchTests(unittest.TestCase):
    def test_replaces_duplicate_urls_preserving_secrets_and_other_settings(self):
        original = "# settings\nMODAL_WHISPER_URL=old\nSUPABASE_JWT_SECRET=keep-private\nMODAL_WHISPER_URL=duplicate\nACTIONS_PROVIDER=openclaw_mcp\n"
        updated = workspaces.update_env(original, {"MODAL_WHISPER_URL": "https://target.modal.run", "MODAL_WORKSPACE": "target"})
        self.assertEqual(updated.count("MODAL_WHISPER_URL="), 1)
        self.assertIn("SUPABASE_JWT_SECRET=keep-private", updated)
        self.assertIn("ACTIONS_PROVIDER=openclaw_mcp", updated)
        self.assertIn("MODAL_WORKSPACE=target", updated)

    def test_unverified_target_does_not_touch_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = root / "manifests"
            state = root / "state"
            workspaces.write_json(manifests / "target.json", {"endpoints": {}})
            workspaces.write_json(state / "target-verification.json", {"ready": False})
            (root / ".env").write_text("KEEP=value\n")
            with patch.object(workspaces, "BACKEND", root), patch.object(workspaces, "MANIFEST_DIR", manifests), patch.object(workspaces, "STATE_DIR", state):
                with self.assertRaises(RuntimeError):
                    workspaces.switch("target")
            self.assertEqual((root / ".env").read_text(), "KEEP=value\n")

    def test_endpoint_changes_invalidate_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspaces.write_json(root / "target.json", {"endpoints": {"changed": "url"}})
            workspaces.write_json(root / "target-verification.json", {"ready": True, "source_sha256": "current", "endpoints_sha256": "old"})
            with patch.object(workspaces, "MANIFEST_DIR", root), patch.object(workspaces, "STATE_DIR", root), patch.object(workspaces, "source_digest", return_value="current"):
                with self.assertRaises(RuntimeError):
                    workspaces.switch("target")

    def test_verified_switch_backs_up_env_and_preserves_openclaw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests, state = root / "manifests", root / "state"
            endpoints = {key: "https://target--test.modal.run" for key in workspaces.SPECS}
            fingerprint = hashlib.sha256(json.dumps(endpoints, sort_keys=True).encode()).hexdigest()
            workspaces.write_json(manifests / "target.json", {"endpoints": endpoints})
            workspaces.write_json(state / "target-verification.json", {"ready": True, "source_sha256": "current", "endpoints_sha256": fingerprint})
            original = "ACTIONS_PROVIDER=openclaw_mcp\nOPENCLAW_GATEWAY_TOKEN=keep-private\nMODAL_TOKEN_ID=old-cli-key\n"
            (root / ".env").write_text(original)
            with patch.object(workspaces, "BACKEND", root), patch.object(workspaces, "MANIFEST_DIR", manifests), patch.object(workspaces, "STATE_DIR", state), patch.object(workspaces, "source_digest", return_value="current"), patch("builtins.print"):
                workspaces.switch("target")
            updated = (root / ".env").read_text()
            self.assertIn("OPENCLAW_GATEWAY_TOKEN=keep-private", updated)
            self.assertIn("ACTIONS_PROVIDER=openclaw_mcp", updated)
            self.assertIn("MODAL_TOKEN_ID=\n", updated)
            self.assertIn("MODAL_WORKSPACE=target", updated)
            backups = list(state.glob("*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), original)


if __name__ == "__main__":
    unittest.main()
