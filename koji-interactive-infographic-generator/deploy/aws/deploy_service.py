"""Authenticated, bounded release receiver. Bind to localhost behind HTTPS Caddy.

Only trusted production jobs receive the token. No PR jobs run on this server.
Activation uses an administrator-installed script, with its existing rollback.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

ROOT = Path(os.getenv("KOJI_DEPLOY_ROOT", "/home/ubuntu/koji"))
PREFIX = "/internal/koji-deploy"
MAX_BYTES = 16 * 1024 * 1024
LOCK = threading.Lock()


def verify_run(run, sha):
    base = "https://api.github.com/repos/R26-SE-041/R26-SE-041/actions/runs/" + run
    def fetch(url):
        with urlopen(Request(url, headers={"Accept": "application/vnd.github+json",
                                         "User-Agent": "koji-release-receiver"}), timeout=20) as response:
            return json.load(response)
    release = fetch(base)
    if (release["head_sha"] != sha or release["event"] not in {"push", "workflow_dispatch"}
        or release["path"] != ".github/workflows/koji-interactive.yml"
        or not (release["head_branch"] == "main" or release["head_branch"].startswith("koji-release-"))):
        raise ValueError("Only the production workflow can release this commit")
    jobs = {job["name"]: job["conclusion"] for job in fetch(base + "/jobs?per_page=100")["jobs"]}
    if any(jobs.get(name) != "success" for name in ("frontend", "backend")):
        raise ValueError("Both test jobs must pass before activation")
    if jobs.get("deploy_models") not in {"success", "skipped"}:
        raise ValueError("Model deployment must finish before activation")


def verify_archive(path, sha):
    with tarfile.open(path) as bundle:
        members = bundle.getmembers()
        if len(members) > 1000 or sum(item.size for item in members) > 64 * 1024 * 1024:
            raise ValueError("Release is too large")
        names = set()
        for item in members:
            parts = PurePosixPath(item.name).parts
            if (not item.isfile() or not parts or item.name.startswith("/") or ".." in parts
                or item.name in names or (item.name != "release.json" and parts[0] not in {"studio", "shared"})):
                raise ValueError("Unsafe release member")
            names.add(item.name)
        manifest = json.load(bundle.extractfile("release.json"))
        if manifest["commit"] != sha or set(manifest["files"]) != names - {"release.json"}:
            raise ValueError("Release manifest does not match the tested commit")
        for name, digest in manifest["files"].items():
            if hashlib.sha256(bundle.extractfile(name).read()).hexdigest() != digest:
                raise ValueError("Release checksum mismatch")


def store_status(stage, status, sha):
    temporary = stage / "status.tmp"
    temporary.write_text(json.dumps({"status": status, "commit": sha}))
    temporary.replace(stage / "status.json")


def activate(stage, sha):
    try:
        with (stage / "activation.log").open("wb") as log:
            result = subprocess.run(["bash", str(stage / "activate.sh"), sha],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                                    env={**os.environ, "KOJI_DEPLOY_ROOT": str(ROOT)})
        status = "success" if result.returncode == 0 else "failure"
    except Exception:
        status = "failure"
    finally:
        store_status(stage, status, sha)
        LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def authorized(self):
        token = os.environ["KOJI_DEPLOY_TOKEN"]
        return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)

    def reply(self, code, body):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.authorized():
            return self.reply(401, {"error": "Unauthorized"})
        match = re.fullmatch(PREFIX + r"/([a-f0-9]{40}-[0-9]+-[0-9]+)", self.path)
        if not match:
            return self.reply(404, {"error": "Unknown release"})
        status = ROOT / "deploy-staging" / match[1] / "status.json"
        if not status.is_file():
            return self.reply(404, {"error": "Unknown release"})
        self.reply(200, json.loads(status.read_text()))

    def do_POST(self):
        if not self.authorized():
            return self.reply(401, {"error": "Unauthorized"})
        sha, run, attempt = (self.headers.get(name, "") for name in
                             ("X-Koji-Commit", "X-Koji-Run", "X-Koji-Attempt"))
        if (self.path != PREFIX or not re.fullmatch(r"[a-f0-9]{40}", sha)
            or not re.fullmatch(r"[0-9]+", run) or not re.fullmatch(r"[0-9]+", attempt)):
            return self.reply(400, {"error": "Invalid release identity"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if not 0 < size <= MAX_BYTES:
            return self.reply(413, {"error": "Invalid release size"})
        if not LOCK.acquire(blocking=False):
            return self.reply(409, {"error": "An activation is running"})
        stage = ROOT / "deploy-staging" / f"{sha}-{run}-{attempt}"
        started = False
        try:
            verify_run(run, sha)
            stage.mkdir(parents=True, exist_ok=False)
            self.connection.settimeout(60)
            remaining = size
            with (stage / "backend.tar.gz").open("wb") as output:
                while remaining:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        raise ValueError("Incomplete release upload")
                    output.write(chunk)
                    remaining -= len(chunk)
            verify_archive(stage / "backend.tar.gz", sha)
            shutil.copyfile(Path(__file__).with_name("activate.sh"), stage / "activate.sh")
            store_status(stage, "running", sha)
            threading.Thread(target=activate, args=(stage, sha), daemon=True).start()
            started = True
            self.reply(202, {"release": stage.name})
        except Exception as error:
            # Do not include upstream URLs, tokens, private configuration or stack traces.
            print("Release rejected:", type(error).__name__, flush=True)
            self.reply(400, {"error": "Release validation failed; inspect the deployment service journal"})
        finally:
            if not started:
                LOCK.release()


if __name__ == "__main__":
    if len(os.environ.get("KOJI_DEPLOY_TOKEN", "")) < 40:
        raise SystemExit("Configure a strong deployment token")
    ThreadingHTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
