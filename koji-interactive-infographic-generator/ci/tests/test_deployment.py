"""Verify monorepo isolation and CPU release artifact safety."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import shlex
from unittest.mock import patch

CI = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, CI / (name + ".py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


changes = module("changes")
package = module("package_backend")
deploy = module("deploy_ec2")


class DeploymentRoutingTests(unittest.TestCase):
    def test_other_components_and_root_docs_do_not_deploy_koji(self):
        result = changes.classify([
            "baskaran-interactive-audio-communication/backend/app/main.py",
            "nishy-adaptive-quiz-recommender/frontend/package.json",
            "sarmitha-image-text-extractor-study-gen/backend/main.py",
            "common-frontend/App.tsx", "README.md", "research-paper/manuscript.tex",
        ])
        self.assertFalse(any(result.values()))

    def test_frontend_change_leaves_ec2_and_models_untouched(self):
        self.assertEqual(changes.classify([changes.PREFIX + "frontend/App.tsx"]),
                         {"frontend": True, "backend": False, "models": False})

    def test_cpu_api_change_does_not_redeploy_frontend_or_gpu(self):
        self.assertEqual(changes.classify([changes.PREFIX + "backend/studio/main.py"]),
                         {"frontend": False, "backend": True, "models": False})

    def test_runtime_agent_rules_are_model_changes(self):
        result = changes.classify([changes.PREFIX + "backend/agents/prompt-agent/SKILL.md"])
        self.assertTrue(result["models"])
        self.assertFalse(result["backend"])

    def test_documentation_and_tests_do_not_publish_apps(self):
        self.assertFalse(any(changes.classify([
            changes.PREFIX + "README.md", changes.PREFIX + "frontend/tests/history.test.cjs",
            changes.PREFIX + "docs/authentication.md",
            changes.PREFIX + "deploy/aws/README.md",
        ]).values()))

    def test_manual_release_does_not_force_paid_model_deployment(self):
        self.assertEqual(changes.classify([], force=True),
                         {"frontend": True, "backend": True, "models": False})


class ReleaseArtifactTests(unittest.TestCase):
    def test_package_contains_only_tracked_cpu_code_with_matching_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            component = root / "koji-interactive-infographic-generator"
            files = {
                "backend/studio/requirements.txt": "requests\n",
                "backend/studio/main.py": "# CPU API\n",
                "backend/shared/safety.py": "# Shared code\n",
                "backend/agents/image-agent/model.py": "# GPU service\n",
                "frontend/App.tsx": "// Client\n",
            }
            for name, content in files.items():
                target = component / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=CI", "-c", "user.email=ci@example.test",
                            "commit", "-qm", "Fixture"], cwd=root, check=True)
            (component / "backend/studio/.env").write_text("PRIVATE=must-not-be-uploaded")
            archive = root / "backend.tar.gz"
            with patch.object(package, "COMPONENT", component):
                commit = package.build_archive(archive)
            deploy.validate_release(archive, commit)
            with tarfile.open(archive) as bundle:
                self.assertEqual(set(bundle.getnames()), {
                    "studio/requirements.txt", "studio/main.py", "shared/safety.py", "release.json",
                })
            with self.assertRaisesRegex(ValueError, "tested commit"):
                deploy.validate_release(archive, "0" * 40)

    def test_remote_deploy_rejects_traversal_and_unrelated_files(self):
        for name in ["../.env", "/etc/passwd", "frontend/App.tsx"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                archive = Path(temporary) / "unsafe.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    content = b"unsafe"
                    entry = tarfile.TarInfo(name)
                    entry.size = len(content)
                    bundle.addfile(entry, io.BytesIO(content))
                with self.assertRaises(ValueError):
                    deploy.validate_release(archive, "0" * 40)


@unittest.skipIf(os.name == "nt", "Activation simulation uses Linux shell tools in CI")
class ActivationTests(unittest.TestCase):
    def exercise_activation(self, fail_health):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = root / "backend"
            stage = root / "deploy-staging" / "fixture"
            tools = root / "tools"
            for directory in [backend / "studio", backend / "shared", backend / ".venv/bin", stage, tools]:
                directory.mkdir(parents=True, exist_ok=True)
            (backend / "studio/main.py").write_text("old API")
            (backend / "shared/safety.py").write_text("old shared code")
            (backend / ".env").write_text("PRIVATE=preserve")
            (backend / "release.json").write_text('{"commit":"previous"}')

            def executable(file, content):
                file.write_text("#!/usr/bin/env bash\n" + content)
                file.chmod(0o755)

            executable(backend / ".venv/bin/python", "exit 0\n")
            (backend / ".venv/original-marker").write_text("original environment")
            import sys
            executable(tools / "python3", (
                'if [[ "$1" == "-m" && "$2" == "venv" ]]; then\n'
                '  mkdir -p "$3/bin"\n'
                '  cp "$KOJI_DEPLOY_ROOT/backend/.venv/bin/python" "$3/bin/python"\n'
                '  exit 0\n'
                'fi\nexec ' + shlex.quote(sys.executable) + ' "$@"\n'
            ))
            executable(tools / "sudo", 'echo "$*" >> "$KOJI_DEPLOY_ROOT/service-actions"\nexit 0\n')
            executable(tools / "systemctl", "exit 0\n")
            executable(tools / "sleep", "exit 0\n")
            executable(tools / "curl", "exit " + ("1" if fail_health else "0") + "\n")
            commit = "a" * 40
            import hashlib
            files = {"studio/main.py": b"new API", "shared/safety.py": b"new shared code",
                     "studio/requirements.txt": b"requests\n"}
            manifest = {"commit": commit, "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
            files["release.json"] = json.dumps(manifest).encode()
            with tarfile.open(stage / "backend.tar.gz", "w:gz") as bundle:
                for name, data in files.items():
                    entry = tarfile.TarInfo(name)
                    entry.size = len(data)
                    bundle.addfile(entry, io.BytesIO(data))
            import shutil
            shutil.copyfile(CI.parent / "deploy/aws/activate.sh", stage / "activate.sh")
            result = subprocess.run(["bash", str(stage / "activate.sh"), commit],
                                    env={**os.environ, "KOJI_DEPLOY_ROOT": str(root),
                                         "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual((backend / ".env").read_text(), "PRIVATE=preserve")
            if fail_health:
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual((backend / "studio/main.py").read_text(), "old API")
                self.assertEqual((backend / "shared/safety.py").read_text(), "old shared code")
                self.assertTrue((backend / ".venv/original-marker").exists())
                self.assertEqual(json.loads((backend / "release.json").read_text())["commit"], "previous")
                self.assertIn("previous backend and environment restored", result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((backend / "studio/main.py").read_text(), "new API")
                self.assertTrue((backend / ".venv").is_symlink())
                self.assertEqual(json.loads((backend / "release.json").read_text())["commit"], commit)
                backups = list((root / "deploy-backups").iterdir())
                self.assertEqual((backups[0] / "studio/main.py").read_text(), "old API")

    def test_success_preserves_env_and_retains_previous_release(self):
        self.exercise_activation(False)

    def test_failed_readiness_restores_source_and_python_environment(self):
        self.exercise_activation(True)


if __name__ == "__main__":
    unittest.main()
