"""Release the tested CPU artifact over the authenticated HTTPS receiver."""
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen


def main():
    origin = os.environ["KOJI_STUDIO_API_URL"].rstrip("/")
    if not origin.startswith("https://"):
        raise SystemExit("Production deployment requires HTTPS")
    endpoint = origin + "/internal/koji-deploy"
    sha, run, attempt = (os.environ[name] for name in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"))
    headers = {"Authorization": "Bearer " + os.environ["KOJI_DEPLOY_TOKEN"],
               "X-Koji-Commit": sha, "X-Koji-Run": run, "X-Koji-Attempt": attempt,
               "Content-Type": "application/gzip"}
    payload = Path(os.environ["KOJI_BACKEND_ARCHIVE"]).read_bytes()
    with urlopen(Request(endpoint, data=payload, headers=headers, method="POST"), timeout=120) as response:
        release = json.load(response)["release"]
    for _ in range(240):
        time.sleep(10)
        with urlopen(Request(endpoint + "/" + release, headers={"Authorization": headers["Authorization"]}), timeout=30) as response:
            status = json.load(response)
        if status["status"] == "success" and status["commit"] == sha:
            print("EC2 API and worker deployed:", sha)
            return
        if status["status"] != "running":
            raise SystemExit("EC2 activation failed; inspect the release log on the server")
    raise SystemExit("EC2 deployment timed out; inspect the server before retrying")


if __name__ == "__main__":
    main()
