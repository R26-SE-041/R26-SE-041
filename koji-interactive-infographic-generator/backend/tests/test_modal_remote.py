import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from studio import modal_remote


class RemoteAccountTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "operator.env").write_text("KOJI_DEPLOY_TOKEN=" + "t" * 64)
        self.config = self.root / "remote.json"
        self.config.write_text(json.dumps({"version": 1, "origin": "https://api.example.com", "token_file": "operator.env"}))
        self.opener = Mock()
        self.opener.open.return_value.__enter__ = Mock(return_value=io.BytesIO(json.dumps({"active_account": "agal-koji"}).encode()))
        self.opener.open.return_value.__exit__ = Mock(return_value=False)
        context = patch.object(modal_remote, "build_opener", return_value=self.opener)
        context.start()
        self.addCleanup(context.stop)

    def test_switch_targets_ec2_not_local_routing(self):
        result = modal_remote.execute("switch", "agal-koji", self.config)
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.example.com/internal/koji-deploy/modal")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {"action": "switch", "account": "agal-koji"})
        self.assertEqual(request.headers["Authorization"], "Bearer " + "t" * 64)
        self.assertEqual(result["active_account"], "agal-koji")

    def test_status_reads_authenticated_remote_state(self):
        modal_remote.execute("status", None, self.config)
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertTrue(request.full_url.endswith("/modal/status"))

    def test_invalid_account_is_rejected_without_network(self):
        with self.assertRaises(ValueError):
            modal_remote.execute("switch", "x; rm -rf /", self.config)
        self.opener.open.assert_not_called()

    def test_http_and_credential_origins_are_rejected(self):
        for origin in ("http://api.example.com", "https://user:pass@api.example.com", "https://api.example.com/path"):
            self.config.write_text(json.dumps({"version": 1, "origin": origin, "token_file": "operator.env"}))
            with self.assertRaises(ValueError):
                modal_remote.execute("status", None, self.config)
        self.opener.open.assert_not_called()

    def test_short_token_is_rejected(self):
        (self.root / "operator.env").write_text("KOJI_DEPLOY_TOKEN=short")
        with self.assertRaises(ValueError):
            modal_remote.execute("status", None, self.config)

    def test_failed_connection_reports_unconfirmed_operation(self):
        self.opener.open.side_effect = URLError("offline")
        with self.assertRaisesRegex(ValueError, "not confirmed"):
            modal_remote.execute("switch", "agal-koji", self.config)

    def test_unauthorized_and_not_installed_have_clear_errors(self):
        for code, message in ((401, "rejected"), (404, "not installed"), (409, "not confirmed")):
            self.opener.open.side_effect = HTTPError("https://api.example.com", code, "error", {}, io.BytesIO(b'{}'))
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, message):
                modal_remote.execute("status", None, self.config)

    def test_administrator_token_is_not_forwarded_on_redirects(self):
        self.assertIsNone(modal_remote.NoRedirects().redirect_request(None, None, 302, "redirect", {}, "https://attacker.example.com"))


if __name__ == "__main__":
    unittest.main()
