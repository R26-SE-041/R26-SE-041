"""Package checked routing/control files for the bounded EC2 installer."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def package(destination: Path) -> None:
    paths = {name: ROOT / "backend" / name for name in (
        "studio/main.py", "studio/pipeline.py", "studio/modal_accounts.py",
        "studio/modal_remote.py", "modal-accounts.json",
    )}
    paths.update({"control/deploy_service.py": ROOT / "deploy/aws/deploy_service.py",
                  "control/switch-modal.sh": ROOT / "deploy/aws/switch-modal.sh"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"files": {}}
    with tarfile.open(destination, "w:gz") as bundle:
        for name, path in paths.items():
            data = path.read_bytes().replace(b"\r\n", b"\n")
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            bundle.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(data)
        bundle.addfile(info, io.BytesIO(data))
    print("Packaged checked routing/control files:", destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/modal-switch.tar.gz")
    package(parser.parse_args().output.resolve())
