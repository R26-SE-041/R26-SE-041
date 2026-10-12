"""Send only the tested component backend to the configured EC2 host."""
import os
import re
import subprocess
import tempfile
from pathlib import Path
import json
import tarfile


def validate_release(archive: Path, sha: str) -> None:
    with tarfile.open(archive) as bundle:
        for entry in bundle.getmembers():
            parts = Path(entry.name).parts
            if not entry.isfile() or entry.name.startswith("/") or ".." in parts:
                raise ValueError("Release contains an unsafe archive member")
            if entry.name != "release.json" and parts[0] not in {"studio", "shared"}:
                raise ValueError("Release contains files outside the CPU backend")
        manifest = json.load(bundle.extractfile("release.json"))
        if manifest["commit"] != sha:
            raise ValueError("Backend artifact does not match the tested commit")

def main():
    sha = os.environ["GITHUB_SHA"]
    host = os.environ["KOJI_EC2_HOST"]
    user = os.environ.get("KOJI_EC2_USER", "ubuntu")
    root = os.environ.get("KOJI_EC2_ROOT", "/home/ubuntu/koji")
    run = os.environ.get("GITHUB_RUN_ID", "manual") + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    if (not re.fullmatch(r"[a-f0-9]{40}", sha)
        or not re.fullmatch(r"[A-Za-z0-9.-]+", host)
        or not re.fullmatch(r"[a-z_][a-z0-9_-]*", user)
        or not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+", root)
        or not re.fullmatch(r"[A-Za-z0-9-]+", run)):
        raise SystemExit("Invalid commit or EC2 hostname")
    component = Path(__file__).resolve().parents[1]
    archive = Path(os.environ["KOJI_BACKEND_ARCHIVE"]).resolve()
    validate_release(archive, sha)
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        key = directory / "key"
        known_hosts = directory / "known_hosts"
        key.write_text(os.environ["KOJI_EC2_SSH_KEY"].strip() + "\n")
        key.chmod(0o600)
        known_hosts.write_text(os.environ["KOJI_EC2_KNOWN_HOSTS"].strip() + "\n")
        options = ["-i", str(key), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                   "-o", f"UserKnownHostsFile={known_hosts}", "-o", "ConnectTimeout=15"]
        target = user + "@" + host
        release = f"{root}/deploy-staging/{sha}-{run}"
        subprocess.run(["ssh", *options, target, f"mkdir -p {release}"], check=True)
        subprocess.run(["scp", *options, str(archive), f"{target}:{release}/backend.tar.gz"], check=True)
        subprocess.run(["scp", *options, str(component / "deploy/aws/activate.sh"),
                        f"{target}:{release}/activate.sh"], check=True)
        subprocess.run(["ssh", *options, target,
            f"KOJI_DEPLOY_ROOT={root} bash {release}/activate.sh {sha}"],
            check=True, timeout=900)

if __name__ == "__main__":
    main()
