"""Production receiver rejects untrusted jobs, tampering and unauthenticated uploads."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SERVICE = Path(__file__).resolve().parents[2] / "deploy/aws/deploy_service.py"
spec = importlib.util.spec_from_file_location("release_receiver", SERVICE)
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


class ReleaseReceiverTests(unittest.TestCase):
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
