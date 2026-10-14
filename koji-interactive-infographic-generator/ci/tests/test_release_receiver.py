"""Production receiver rejects untrusted jobs, tampering and unauthenticated uploads."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

SERVICE = Path(__file__).resolve().parents[2] / "deploy/aws/deploy_service.py"
spec = importlib.util.spec_from_file_location("release_receiver", SERVICE)
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


class ReleaseReceiverTests(unittest.TestCase):
    def modal_handler(self, action="switch", account="agal-koji"):
        handler = object.__new__(receiver.Handler)
        handler.path = receiver.PREFIX + "/modal"
        body = json.dumps({"action": action, "account": account}).encode()
        handler.headers = {"Authorization": "Bearer " + "t" * 64, "Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.connection = Mock()
        handler.reply = Mock()
        return handler

    def test_remote_switch_requires_authorization(self):
        handler = self.modal_handler()
        handler.headers["Authorization"] = "Bearer wrong"
        with patch.dict(receiver.os.environ, {"KOJI_DEPLOY_TOKEN": "t" * 64}), patch.object(receiver.subprocess, "run") as run:
            handler.do_POST()
        handler.reply.assert_called_once_with(401, {"error": "Unauthorized"})
        run.assert_not_called()

    def test_remote_switch_runs_only_checked_backend_command(self):
        handler = self.modal_handler()
        result = Mock(returncode=0, stdout=json.dumps({"active_account": "agal-koji"}))
        with patch.dict(receiver.os.environ, {"KOJI_DEPLOY_TOKEN": "t" * 64}), patch.object(receiver.subprocess, "run", return_value=result) as run:
            handler.do_POST()
        command = run.call_args.args[0]
        self.assertEqual(command[1:], ["-m", "studio.modal_accounts", "--json", "switch", "agal-koji"])
        self.assertNotIn("KOJI_DEPLOY_TOKEN", run.call_args.kwargs["env"])
        handler.reply.assert_called_once_with(200, {"active_account": "agal-koji"})

    def test_remote_command_injection_and_oversized_body_are_rejected(self):
        for action, account in (("shell", "agal-koji"), ("switch", "agal-koji;whoami"), ("rollback", "agal-koji")):
            handler = self.modal_handler(action, account)
            with patch.dict(receiver.os.environ, {"KOJI_DEPLOY_TOKEN": "t" * 64}), patch.object(receiver.subprocess, "run") as run:
                handler.do_POST()
            self.assertEqual(handler.reply.call_args.args[0], 400)
            run.assert_not_called()
        handler = self.modal_handler()
        handler.headers["Content-Length"] = "2048"
        with patch.dict(receiver.os.environ, {"KOJI_DEPLOY_TOKEN": "t" * 64}):
            handler.do_POST()
        self.assertEqual(handler.reply.call_args.args[0], 413)

    def test_remote_health_failure_returns_conflict_and_releases_lock(self):
        handler = self.modal_handler()
        result = Mock(returncode=1, stdout=json.dumps({"details": ["image: unavailable"]}))
        with patch.dict(receiver.os.environ, {"KOJI_DEPLOY_TOKEN": "t" * 64}), patch.object(receiver.subprocess, "run", return_value=result):
            handler.do_POST()
        self.assertEqual(handler.reply.call_args.args[0], 409)
        self.assertFalse(receiver.LOCK.locked())

    def test_remote_switch_cannot_overlap_release_activation(self):
        handler = self.modal_handler()
        receiver.LOCK.acquire()
        try:
            with patch.dict(receiver.os.environ, {"KOJI_DEPLOY_TOKEN": "t" * 64}), patch.object(receiver.subprocess, "run") as run:
                handler.do_POST()
            self.assertEqual(handler.reply.call_args.args[0], 409)
            run.assert_not_called()
        finally:
            receiver.LOCK.release()

    def test_archive_rejects_tampering_and_unlisted_files(self):
        sha = "a" * 40
        for changed, extra in ((False, False), (True, False), (False, True)):
            with self.subTest(changed=changed, extra=extra), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "release.tar.gz"
                files = {"studio/main.py": b"tested code"}
                manifest = {"commit": sha, "files": {name: hashlib.sha256(data).hexdigest()
                                                    for name, data in files.items()}}
                if changed:
                    files["studio/main.py"] = b"unreviewed code"
                if extra:
                    files["studio/extra.py"] = b"not in manifest"
                files["release.json"] = json.dumps(manifest).encode()
                with tarfile.open(path, "w:gz") as bundle:
                    for name, data in files.items():
                        item = tarfile.TarInfo(name)
                        item.size = len(data)
                        bundle.addfile(item, io.BytesIO(data))
                if changed or extra:
                    with self.assertRaises(ValueError):
                        receiver.verify_archive(path, sha)
                else:
                    receiver.verify_archive(path, sha)

    def test_jobs_require_trusted_workflow_and_passed_tests_and_models(self):
        sha = "a" * 40
        for branch, event, tests, models, allowed in (
            ("main", "push", "success", "success", True),
            ("main", "push", "success", "skipped", True),
            ("topic", "push", "success", "success", False),
            ("main", "pull_request", "success", "success", False),
            ("main", "push", "failure", "success", False),
            ("main", "push", "success", "failure", False),
            ("main", "push", "success", None, False),
        ):
            metadata = {"head_sha": sha, "head_branch": branch, "event": event,
                        "path": ".github/workflows/koji-interactive.yml"}
            jobs = {"jobs": [{"name": name, "conclusion": result} for name, result in
                             (("frontend", "success"), ("backend", tests), ("deploy_models", models))]}
            responses = [io.BytesIO(json.dumps(item).encode()) for item in (metadata, jobs)]
            with self.subTest(branch=branch, event=event, tests=tests, models=models), patch.object(receiver, "urlopen", side_effect=responses):
                if allowed:
                    receiver.verify_run("123", sha)
                else:
                    with self.assertRaises(ValueError):
                        receiver.verify_run("123", sha)

    def test_receiver_requires_token_before_processing_upload(self):
        handler = object.__new__(receiver.Handler)
        handler.headers = {"Authorization": "Bearer wrong"}
        responses = []
        handler.reply = lambda code, body: responses.append(code)
        with patch.dict(receiver.os.environ, {"KOJI_DEPLOY_TOKEN": "x" * 48}), patch.object(receiver, "verify_run") as verify:
            handler.do_POST()
        self.assertEqual(responses, [401])
        verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
