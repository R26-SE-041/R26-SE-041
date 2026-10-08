"""Deploy only affected Koji model services; never warm GPUs or download weights."""
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
MODELS={"prompt":"prompt-agent","image":"image-agent","sketch":"sketch-agent","interactive":"interactive-agent","evaluation":"eval-agent","threed":"threed-agent"}
before=os.getenv("BEFORE_SHA","")
force=os.getenv("FORCE_MODEL_DEPLOY","").lower()=="true"
if force or not before or set(before)=={"0"}:
    changed=None
else:
    changed=subprocess.check_output(["git","diff","--name-only",before,os.environ["GITHUB_SHA"],"--","koji-interactive-infographic-generator/backend"],cwd=ROOT,text=True).splitlines()
for name,agent in MODELS.items():
    affected=changed is None or any("/agents/"+agent+"/" in path or "/backend/shared/" in path or "/backend/anatomy/" in path for path in changed)
    if affected:
        subprocess.run([sys.executable,"-m","modal","deploy","agents/"+agent+"/modal_app.py"],cwd=ROOT/"backend",check=True)
