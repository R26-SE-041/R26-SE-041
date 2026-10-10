"""Backend CI checks scoped to Koji; no model/GPU calls."""
from pathlib import Path
import compileall
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
for directory in ("studio", "shared", "agents"):
    if not compileall.compile_dir(ROOT / "backend" / directory, quiet=1):
        raise SystemExit(1)
subprocess.run([sys.executable,"-m","pytest",
    "tests/test_studio.py","tests/test_studio_auth.py","tests/test_vercel_routing.py","tests/test_studio_conversations.py","tests/test_studio_repository.py","tests/test_sketch.py",
    "tests/test_image_policies.py","tests/test_auto_labeling.py","tests/test_label_placement.py"],
    cwd=ROOT / "backend",check=True)
