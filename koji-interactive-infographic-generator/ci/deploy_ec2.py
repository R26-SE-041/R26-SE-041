"""Send only the tested component backend to the configured EC2 host."""
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

def main():
    sha = os.environ["GITHUB_SHA"]
    host = os.environ["KOJI_EC2_HOST"]
    if not re.fullmatch(r"[a-f0-9]{40}", sha) or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise SystemExit("Invalid commit or EC2 hostname")
    component = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        key = directory / "key"
        known_hosts = directory / "known_hosts"
        key.write_text(os.environ["KOJI_EC2_SSH_KEY"].strip() + "\n")
        key.chmod(0o600)
        known_hosts.write_text(os.environ["KOJI_EC2_KNOWN_HOSTS"].strip() + "\n")
        options = ["-i", str(key), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                   "-o", f"UserKnownHostsFile={known_hosts}", "-o", "ConnectTimeout=15"]
        target = "koji@" + host
        archive = directory / "backend.tar.gz"
        # Restrict deployment to tracked files from the already tested checkout.
        tracked = subprocess.check_output(["git", "ls-files", "-z", "--",
            str(component / "backend"), str(component / "deploy/aws/activate.sh")]).split(b"\0")
        with tarfile.open(archive, "w:gz") as bundle:
            for raw in tracked:
                if not raw:
                    continue
                source = Path(os.fsdecode(raw)).resolve()
                relative = source.relative_to(component)
                if source.is_file() and not source.is_symlink():
                    bundle.add(source, arcname=str(relative), recursive=False)
        release = f"/opt/koji/releases/{sha}"
        subprocess.run(["ssh", *options, target, f"mkdir -p {release}"], check=True)
        subprocess.run(["scp", *options, str(archive), f"{target}:{release}/backend.tar.gz"], check=True)
        subprocess.run(["ssh", *options, target,
            f"tar -xzf {release}/backend.tar.gz -C {release} && bash {release}/deploy/aws/activate.sh {sha}"],
            check=True, timeout=900)

if __name__ == "__main__":
    main()
