"""Package tracked CPU API/worker code, never credentials or GPU services."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

COMPONENT = Path(__file__).resolve().parents[1]


def build_archive(destination: Path) -> str:
    repository = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=COMPONENT, text=True
    ).strip())
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    prefix = COMPONENT.relative_to(repository).as_posix() + "/backend/"
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", prefix + "studio", prefix + "shared"],
        cwd=repository,
    ).split(b"\0")
    manifest = {"commit": commit, "files": {}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as bundle:
        for raw in tracked:
            if not raw:
                continue
            source = repository / raw.decode("utf-8")
            name = source.relative_to(COMPONENT / "backend").as_posix()
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Release input must be a regular file: {name}")
            if source.name == ".env" or source.suffix in {".pem", ".key"}:
                raise ValueError("Credentials cannot be packaged")
            content = source.read_bytes()
            manifest["files"][name] = hashlib.sha256(content).hexdigest()
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            entry.mode = 0o644
            bundle.addfile(entry, io.BytesIO(content))
        if "studio/requirements.txt" not in manifest["files"]:
            raise ValueError("CPU backend requirements are missing")
        content = json.dumps(manifest, indent=2).encode()
        entry = tarfile.TarInfo("release.json")
        entry.size = len(content)
        entry.mode = 0o644
        bundle.addfile(entry, io.BytesIO(content))
    return commit


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    print("Packaged CPU backend commit", build_archive(arguments.destination))
