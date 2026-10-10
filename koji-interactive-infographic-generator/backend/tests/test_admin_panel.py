import copy
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
for path in (str(BACKEND_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import admin_panel  # noqa: E402


SKILL_CANDIDATE = {
    "version": 4,
    "content": "# SKILL.md\n\nGrammar Rules\n...",
    "status": "candidate",
    "old_score": 6.5,
    "new_score": 8.1,
    "validation_count": 10,
    "feedback_pattern_ids": [],
    "created_at": "2026-08-30",
}

MEMORY_CANDIDATE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "fingerprint": "fp",
    "scope": "agent",
    "agent_name": "prompt-agent",
    "memory_type": "memento",
    "content": "Preserve the user's requested subject during enhancement.",
    "confidence": 0.87,
    "evidence_count": 12,
    "status": "proposed",
    "source_candidate_id": None,
    "metadata": {},
    "created_at": "2026-08-30",
    "updated_at": "2026-08-30",
    "deployed_at": None,
}


class AdminPanelServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), admin_panel.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    @patch("admin_panel.list_agent_memories", return_value=[MEMORY_CANDIDATE])
    @patch("admin_panel.list_skill_versions", return_value=[SKILL_CANDIDATE])
    def test_dashboard_lists_pending_candidates(self, list_skill, list_memory) -> None:
        with urllib.request.urlopen(self._url("/")) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
        self.assertIn("/skill/4", body)
        self.assertIn("/memory/11111111-1111-1111-1111-111111111111", body)

    @patch("admin_panel.get_skill_version", return_value=SKILL_CANDIDATE)
    def test_skill_detail_shows_approve_form_for_a_candidate(self, get_skill) -> None:
        with urllib.request.urlopen(self._url("/skill/4")) as response:
            body = response.read().decode("utf-8")
        self.assertIn("Approve &amp; Deploy", body)
        self.assertIn("Grammar Rules", body)

    @patch("admin_panel.get_skill_version", return_value=None)
    def test_skill_detail_404s_for_unknown_version(self, get_skill) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url("/skill/999"))
        self.assertEqual(ctx.exception.code, 404)

    @patch("admin_panel.subprocess.run")
    def test_approve_skill_success_redirects_with_message(self, run) -> None:
        run.return_value.returncode = 0
        run.return_value.stdout = "deployed"
        run.return_value.stderr = ""

        opener = urllib.request.build_opener(_NoRedirect)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(urllib.request.Request(self._url("/skill/4/approve"), method="POST", data=b""))

        self.assertEqual(ctx.exception.code, 303)
        self.assertIn("deployed", ctx.exception.headers["Location"])
        called_args = run.call_args.args[0]
        self.assertIn("approve_skill_version", " ".join(called_args))
        self.assertIn("4", called_args)

    @patch("admin_panel.subprocess.run")
    def test_approve_skill_failure_shows_error_not_redirect(self, run) -> None:
        run.return_value.returncode = 1
        run.return_value.stdout = ""
        run.return_value.stderr = "modal: version 4 is not an activatable candidate"

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(
                urllib.request.Request(self._url("/skill/4/approve"), method="POST", data=b"")
            )
        self.assertEqual(ctx.exception.code, 500)
        body = ctx.exception.read().decode("utf-8")
        self.assertIn("not an activatable candidate", body)

    @patch("admin_panel.transition_agent_memory", return_value={"status": "approved"})
    def test_transition_memory_calls_db_and_redirects(self, transition) -> None:
        opener = urllib.request.build_opener(_NoRedirect)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(
                urllib.request.Request(
                    self._url("/memory/11111111-1111-1111-1111-111111111111/transition"),
                    method="POST",
                    data=b"status=approved",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            )
        self.assertEqual(ctx.exception.code, 303)
        transition.assert_called_once_with("11111111-1111-1111-1111-111111111111", "approved")

    def test_unknown_path_is_404(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url("/nope"))
        self.assertEqual(ctx.exception.code, 404)


class AdminPanelDemoModeTests(unittest.TestCase):
    """No DATABASE_URL available -> DEMO_MODE serves fixed sample data and
    never touches subprocess/modal or the real DB, even when actions are
    triggered through real HTTP requests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), admin_panel.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def setUp(self) -> None:
        admin_panel.DEMO_MODE = True
        self._skills_snapshot = copy.deepcopy(admin_panel._DEMO_SKILLS)
        self._memories_snapshot = copy.deepcopy(admin_panel._DEMO_MEMORIES)

    def tearDown(self) -> None:
        admin_panel.DEMO_MODE = False
        admin_panel._DEMO_SKILLS[:] = self._skills_snapshot
        admin_panel._DEMO_MEMORIES[:] = self._memories_snapshot

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_dashboard_shows_demo_banner_and_only_pending_sample_rows(self) -> None:
        with urllib.request.urlopen(self._url("/")) as response:
            body = response.read().decode("utf-8")
        self.assertIn("DEMO MODE", body)
        self.assertIn("/skill/7", body)  # candidate in the fixtures
        self.assertNotIn("/skill/6", body)  # already-deployed fixture must not show as pending

    @patch("admin_panel.subprocess.run")
    def test_approve_skill_in_demo_mode_never_calls_subprocess(self, run) -> None:
        opener = urllib.request.build_opener(_NoRedirect)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(urllib.request.Request(self._url("/skill/7/approve"), method="POST", data=b""))
        self.assertEqual(ctx.exception.code, 303)
        run.assert_not_called()
        row = next(r for r in admin_panel._DEMO_SKILLS if r["version"] == 7)
        self.assertEqual(row["status"], "deployed")

    @patch("admin_panel.transition_agent_memory")
    def test_transition_memory_in_demo_mode_never_calls_real_db(self, transition) -> None:
        opener = urllib.request.build_opener(_NoRedirect)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(
                urllib.request.Request(
                    self._url("/memory/demo-mem-1/transition"),
                    method="POST",
                    data=b"status=approved",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            )
        self.assertEqual(ctx.exception.code, 303)
        transition.assert_not_called()
        row = next(r for r in admin_panel._DEMO_MEMORIES if r["id"] == "demo-mem-1")
        self.assertEqual(row["status"], "approved")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


if __name__ == "__main__":
    unittest.main()
