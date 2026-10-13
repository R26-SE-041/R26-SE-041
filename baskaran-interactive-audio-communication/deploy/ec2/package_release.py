"""Create a source-only EC2 release; never includes local users, models or secrets."""
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / ".workspace-runtime" / "voicelearn-ec2-source.tar.gz"
ALLOWED = ["backend/app", "backend/modal_endpoints", "backend/modal_workspaces", "backend/scripts",
           "backend/Dockerfile.ec2", "backend/Dockerfile.ec2.dockerignore", "backend/requirements-cloud.txt", "backend/openclaw_mcp.py", "deploy/ec2"]


def source_files():
    for relative in ALLOWED:
        path = ROOT / relative
        for file in (sorted(path.rglob('*')) if path.is_dir() else [path]):
            if not file.is_file() or file.is_symlink():
                continue
            name = file.relative_to(ROOT)
            if any(part.startswith('.') or part == '__pycache__' for part in name.parts):
                continue
            if file.suffix in {'.pyc', '.pyo', '.gz'}:
                continue
            yield file, name.as_posix()


if __name__ == '__main__':
    OUTPUT.parent.mkdir(exist_ok=True)
    files = list(source_files())
    with tarfile.open(OUTPUT, 'w:gz') as archive:
        for file, name in files:
            archive.add(file, arcname=name, recursive=False)
    print(f"Packaged {len(files)} source files: {OUTPUT.name}. No runtime data included.")
