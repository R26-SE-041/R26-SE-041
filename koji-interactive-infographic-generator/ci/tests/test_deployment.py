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
import re
import yaml
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
    def test_main_push_keeps_changes_from_cancelled_or_failed_earlier_pushes(self):
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"push","GITHUB_REF":"refs/heads/main",
                "GITHUB_SHA":"current","BEFORE_SHA":"immediate-parent","GITHUB_OUTPUT":""},clear=True), \
                patch.object(changes,"successful_push_base",return_value="last-success"), \
                patch.object(changes.subprocess,"check_output",return_value=
                    changes.PREFIX+"backend/studio/main.py\n"+changes.PREFIX+"frontend/App.tsx\n") as diff, \
                patch("sys.stdout",new_callable=io.StringIO) as output:
            changes.main()
        self.assertIn("backend=true",output.getvalue())
        self.assertIn("frontend=true",output.getvalue())
        self.assertEqual(diff.call_args.args[0],["git","diff","--name-only","last-success","current"])

    def test_baseline_outage_falls_back_to_full_checks(self):
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"push","GITHUB_REF":"refs/heads/main",
                "GITHUB_SHA":"current","BEFORE_SHA":"parent","GITHUB_OUTPUT":""},clear=True), \
                patch.object(changes,"successful_push_base",return_value=None), \
                patch("sys.stdout",new_callable=io.StringIO) as output:
            changes.main()
        self.assertIn("frontend_tests=true",output.getvalue())
        self.assertIn("backend_tests=true",output.getvalue())

    def test_successful_baseline_is_a_valid_ancestor_and_api_failure_is_safe(self):
        head,base = "b"*40,"a"*40
        payload = json.dumps({"workflow_runs":[{"head_sha":head},{"head_sha":"invalid"},{"head_sha":base}]}).encode()
        with patch.dict(os.environ,{"GITHUB_REPOSITORY":"owner/repo","GITHUB_TOKEN":"test-token"},clear=True), \
                patch.object(changes,"urlopen",return_value=io.BytesIO(payload)) as request, \
                patch.object(changes.subprocess,"run") as ancestor:
            ancestor.return_value.returncode = 0
            self.assertEqual(changes.successful_push_base(head),base)
            self.assertIn("status=success",request.call_args.args[0].full_url)
            ancestor.assert_called_once_with(["git","merge-base","--is-ancestor",base,head],capture_output=True,check=False)
        with patch.dict(os.environ,{"GITHUB_REPOSITORY":"owner/repo","GITHUB_TOKEN":"test-token"},clear=True), \
                patch.object(changes,"urlopen",side_effect=OSError("unavailable")), \
                patch("sys.stdout",new_callable=io.StringIO):
            self.assertIsNone(changes.successful_push_base(head))

    def test_checks_follow_changed_components_and_model_changes_require_backend_checks(self):
        scenarios = [
            (["frontend/App.tsx"], {"frontend_tests":True,"backend_tests":False}),
            (["backend/studio/main.py"], {"frontend_tests":False,"backend_tests":True}),
            (["backend/agents/sketch-agent/modal_app.py"], {"frontend_tests":False,"backend_tests":True}),
            (["README.md"], {"frontend_tests":False,"backend_tests":False}),
        ]
        for paths, expected in scenarios:
            paths = [changes.PREFIX + path for path in paths]
            with self.subTest(paths=paths):
                self.assertEqual(changes.test_targets(paths, changes.classify(paths)),expected)

    def test_test_only_edits_run_checks_without_publishing(self):
        for path, target in (("frontend/tests/history.test.cjs","frontend_tests"),
                             ("backend/tests/test_studio.py","backend_tests")):
            paths = [changes.PREFIX + path]
            release = changes.classify(paths)
            self.assertFalse(any(release.values()))
            self.assertTrue(changes.test_targets(paths,release)[target])

    def test_manual_frontend_release_can_also_validate_explicit_model_deployment(self):
        with patch.dict(os.environ,{"GITHUB_EVENT_NAME":"workflow_dispatch","GITHUB_SHA":"commit",
                "DEPLOY_TARGET":"frontend","FORCE_MODEL_DEPLOY":"true","GITHUB_OUTPUT":""},clear=True), \
                patch("sys.stdout",new_callable=io.StringIO) as output:
            changes.main()
        plan = dict(line.split("=") for line in output.getvalue().splitlines())
        self.assertEqual(plan,{"frontend":"true","backend":"false","models":"true",
                               "frontend_tests":"true","backend_tests":"true"})

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


class WorkflowEfficiencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load((CI.parents[1] / ".github/workflows/koji-interactive.yml").read_text())

    def permitted(self, job, *, frontend=False, backend=False, models=False, results=None):
        plan = {"frontend":frontend,"backend":backend,"models":models,
                "frontend_tests":frontend,"backend_tests":backend or models}
        values = {f"needs.changes.outputs.{key}":str(value).lower() for key,value in plan.items()}
        outcomes = {"changes":"success","frontend":"success",
                    "frontend_checks":"success" if frontend else "skipped",
                    "backend":"success" if backend or models else "skipped",
                    "deploy_models":"skipped","deploy_backend":"success" if backend else "skipped"}
        outcomes.update(results or {})
        values.update({f"needs.{key}.result":value for key,value in outcomes.items()})
        values.update({"github.ref":"refs/heads/main","github.event_name":"push",
                       "vars.KOJI_EC2_DEPLOY_ENABLED":"true","vars.KOJI_DEPLOY_ENABLED":"true",
                       "vars.KOJI_MODEL_DEPLOY_ENABLED":"true","inputs.deploy_models":False})
        expression = self.workflow["jobs"][job]["if"]
        expression = re.sub(r"needs\.\w+\.(?:outputs\.\w+|result)|github\.\w+|vars\.\w+|inputs\.\w+",
                            lambda match:repr(values[match.group()]),expression)
        return eval(expression.replace("&&"," and ").replace("||"," or "),
                    {"__builtins__":{}},{"always":lambda:True,"startsWith":lambda value,prefix:value.startswith(prefix)})

    def test_single_component_deployments_allow_unneeded_checks_to_be_skipped(self):
        self.assertTrue(self.permitted("frontend",backend=True))
        self.assertFalse(self.permitted("frontend",frontend=True,results={"frontend_checks":"failure"}))
        self.assertTrue(self.permitted("deploy_frontend",frontend=True))
        self.assertFalse(self.permitted("deploy_backend",frontend=True))
        self.assertTrue(self.permitted("deploy_backend",backend=True))
        self.assertFalse(self.permitted("deploy_frontend",backend=True))
        self.assertTrue(self.permitted("deploy_models",models=True))

    def test_failed_or_cancelled_required_checks_block_deployment(self):
        for outcome in ("failure","cancelled","skipped"):
            for job in ("deploy_frontend","deploy_backend","deploy_models"):
                with self.subTest(outcome=outcome,job=job):
                    self.assertFalse(self.permitted(job,frontend=True,backend=True,models=True,
                                                   results={"backend":outcome}))
        self.assertFalse(self.permitted("deploy_frontend",frontend=True,backend=True,
                                       results={"deploy_backend":"failure"}))

    def test_new_push_cancels_checks_without_interrupting_production_deployments(self):
        self.assertNotIn("concurrency",self.workflow)
        jobs = self.workflow["jobs"]
        for job,output in (("frontend_checks","frontend_tests"),("backend","backend_tests")):
            self.assertEqual(jobs[job]["needs"],"changes")
            self.assertEqual(jobs[job]["if"],f"needs.changes.outputs.{output} == 'true'")
            self.assertIs(jobs[job]["concurrency"]["cancel-in-progress"],True)
        for job in ("deploy_frontend","deploy_backend","deploy_models"):
            self.assertIs(jobs[job]["concurrency"]["cancel-in-progress"],False)

    def test_ci_caches_lightweight_dependencies_and_does_not_install_torch(self):
        steps = self.workflow["jobs"]["backend"]["steps"]
        setup = next(step for step in steps if step.get("uses","").startswith("actions/setup-python@"))
        self.assertEqual(setup["with"]["cache"],"pip")
        self.assertIn("requirements-core.txt",setup["with"]["cache-dependency-path"])
        self.assertIn("requirements-test.txt",setup["with"]["cache-dependency-path"])
        installs = [step["run"] for step in steps if "pip install" in step.get("run","")]
        self.assertEqual(installs,["python -m pip install -r studio/requirements-test.txt"])
        core = (CI.parent/"backend/studio/requirements-core.txt").read_text()
        tests = (CI.parent/"backend/studio/requirements-test.txt").read_text()
        self.assertNotIn("torch",core+tests)
        self.assertNotIn("sentence-transformers",core+tests)
        self.assertIn("sentence-transformers",(CI.parent/"backend/studio/requirements.txt").read_text())


class ReleaseArtifactTests(unittest.TestCase):
    def test_package_contains_only_tracked_cpu_code_with_matching_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            component = root / "koji-interactive-infographic-generator"
            files = {
                "backend/studio/requirements.txt": "-r requirements-core.txt\nsentence-transformers\n",
                "backend/studio/requirements-core.txt": "requests\n",
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
                    "studio/requirements.txt", "studio/requirements-core.txt", "studio/main.py", "shared/safety.py", "release.json",
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
            # Repeated releases must not exhaust the host's disk. Retain the two
            # latest rollback environments and never prune an unmanaged folder.
            environments = root / "deploy-environments"
            environments.mkdir()
            backups = root / "deploy-backups"
            backups.mkdir()
            for index in range(4):
                name = str(index) * 40 + ".abcdefgh"
                old_environment = environments / name
                old_environment.mkdir()
                old_backup = backups / name
                old_backup.mkdir()
                (old_backup / "release.json").write_text('{}')
                (old_backup / ".venv").symlink_to(old_environment, target_is_directory=True)
                os.utime(old_backup, (index + 1, index + 1))
            (environments / "operator-managed").mkdir()

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
            for index in range(4):
                name = str(index) * 40 + ".abcdefgh"
                self.assertEqual((environments / name).exists(), index >= 2)
                self.assertEqual((backups / name).exists(), index >= 2)
            self.assertTrue((environments / "operator-managed").is_dir())
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
                release_backups = [path for path in backups.iterdir() if (path / "studio/main.py").is_file()]
                self.assertEqual(len(release_backups), 1)
                self.assertEqual((release_backups[0] / "studio/main.py").read_text(), "old API")

    def test_success_preserves_env_and_retains_previous_release(self):
        self.exercise_activation(False)

    def test_failed_readiness_restores_source_and_python_environment(self):
        self.exercise_activation(True)


if __name__ == "__main__":
    unittest.main()
