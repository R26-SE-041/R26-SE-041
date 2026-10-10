"""Launch the adapter with optional isolated dependencies, keeping backend deps intact."""

from pathlib import Path
import os
import runpy
import site
import sys

root = Path(__file__).resolve().parent
dependencies = root / ".actions-runtime" / "python"
if dependencies.is_dir():
    site.addsitedir(str(dependencies))  # Process pywin32's Windows DLL/site hooks.
    sys.path.remove(str(dependencies))
    sys.path.insert(0, str(dependencies))
from dotenv import dotenv_values

# Load only adapter settings; unrelated backend credentials are not exported.
values = dotenv_values(root / ".env")
for key in ("ACTIONS_BRIDGE_SECRET", "VOICELEARN_BACKEND_URL", "ACTIONS_TIMEOUT_SECONDS", "ACTIONS_SECTIONED_TIMEOUT_SECONDS"):
    if values.get(key):
        os.environ.setdefault(key, values[key])
runpy.run_path(str(root / "openclaw_mcp.py"), run_name="__main__")
