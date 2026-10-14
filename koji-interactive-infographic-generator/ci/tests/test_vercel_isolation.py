"""Exercise the external audio project's ignore command against real Git changes."""
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[3]
AUDIO = "baskaran-interactive-audio-communication"


class VercelIsolationTests(unittest.TestCase):
    def test_audio_build_filter_from_supported_project_roots(self):
        configs = [REPOSITORY / AUDIO / "vercel.json",
                   REPOSITORY / AUDIO / "frontend/vercel.json"]
        commands = [json.loads(path.read_text())["ignoreCommand"] for path in configs]
        self.assertEqual(commands[0], commands[1])
        command = shlex.split(commands[0])
        cases = [
            ("koji-interactive-infographic-generator/frontend/App.tsx", False),
            ("koji-interactive-infographic-generator/backend/studio/main.py", False),
            ("learnx-project-website/index.html", False),
            (AUDIO + "/frontend/app/page.tsx", True),
            (AUDIO + "/backend/main.py", True),
        ]
        for changed_path, build_expected in cases:
            with self.subTest(changed_path=changed_path), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def git(*args):
                    return subprocess.run(["git", *args], cwd=root, check=True,
                                          capture_output=True, text=True)

                git("init", "-q")
                frontend = root / AUDIO / "frontend"
                frontend.mkdir(parents=True)
                (frontend / "baseline.txt").write_text("baseline")
                git("add", ".")
                git("-c", "user.name=CI", "-c", "user.email=ci@example.test",
                    "commit", "-qm", "Baseline")
                changed = root / changed_path
                changed.parent.mkdir(parents=True, exist_ok=True)
                changed.write_text("change")
                git("add", ".")
                git("-c", "user.name=CI", "-c", "user.email=ci@example.test",
                    "commit", "-qm", "Change")
                for cwd in [root, root / AUDIO, frontend]:
                    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
                    # Vercel: exit 0 skips the build; exit 1 builds changed code.
                    self.assertEqual(result.returncode, int(build_expected), result.stderr)


if __name__ == "__main__":
    unittest.main()
