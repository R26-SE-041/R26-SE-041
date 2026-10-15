"""Classify Koji deployment changes without triggering other components."""
from __future__ import annotations

import os
import json
import re
from pathlib import Path
import subprocess
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PREFIX = "koji-interactive-infographic-generator/"
WORKFLOW = ".github/workflows/koji-interactive.yml"


def classify(paths: list[str], force: bool = False) -> dict[str, bool]:
    result = {"frontend": force, "backend": force, "models": False}
    for path in paths:
        if path == WORKFLOW or path.startswith(PREFIX + "ci/"):
            result["frontend"] = result["backend"] = True
        elif path.startswith(PREFIX + "frontend/"):
            if not path.endswith(".md") and "/tests/" not in path:
                result["frontend"] = True
        elif path.startswith(PREFIX + "deploy/aws/"):
            if not path.endswith(".md"):
                result["backend"] = True
        elif path.startswith((PREFIX + "backend/studio/", PREFIX + "backend/shared/")):
            if not path.endswith(".md"):
                result["backend"] = True
            if path.startswith(PREFIX + "backend/shared/"):
                result["models"] = True
        elif path.startswith((PREFIX + "backend/agents/", PREFIX + "backend/anatomy/",
                              PREFIX + "backend/config/", PREFIX + "backend/skills/")):
            result["models"] = True
    return result


def test_targets(paths: list[str], changes: dict[str, bool]) -> dict[str, bool]:
    """Test-only edits run checks without requesting a production release."""
    return {
        "frontend_tests": changes["frontend"] or any(path.startswith(PREFIX + "frontend/tests/") for path in paths),
        "backend_tests": changes["backend"] or changes["models"] or
            any(path.startswith(PREFIX + "backend/tests/") for path in paths),
    }


def successful_push_base(head: str) -> str | None:
    """Include changes from failed/cancelled pushes until a full run succeeds.

    Comparing only event.before can lose a backend change when a later frontend
    push cancels its checks. A missing baseline safely requests both components.
    """
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repository or not token:
        return None
    params = urlencode({"branch":"main","event":"push","status":"success","per_page":20})
    request = Request(f"https://api.github.com/repos/{repository}/actions/workflows/{Path(WORKFLOW).name}/runs?{params}",
        headers={"Accept":"application/vnd.github+json","Authorization":"Bearer " + token})
    try:
        with urlopen(request,timeout=15) as response:
            runs = json.load(response)["workflow_runs"]
        for run in runs:
            candidate = run.get("head_sha", "")
            if candidate == head or not re.fullmatch(r"[0-9a-f]{40}",candidate):
                continue
            if subprocess.run(["git","merge-base","--is-ancestor",candidate,head],
                              capture_output=True,check=False).returncode == 0:
                return candidate
    except (OSError,ValueError,KeyError,TypeError):
        print("Successful-run baseline unavailable; running all component checks.")
    return None


def main() -> None:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    force = event == "workflow_dispatch" or os.environ.get("GITHUB_REF", "").startswith("refs/tags/")
    before = os.environ.get("BEFORE_SHA", "")
    after = os.environ["GITHUB_SHA"]
    if event == "pull_request":
        before = os.environ["PR_BASE_SHA"]
        after = os.environ["PR_HEAD_SHA"]
    elif event == "push" and os.environ.get("GITHUB_REF") == "refs/heads/main":
        before = successful_push_base(after) or ""
    if force or not before or set(before) == {"0"}:
        paths = []
        force = True
    else:
        paths = subprocess.check_output(
            ["git", "diff", "--name-only", before, after], text=True
        ).splitlines()
    changes = classify(paths, force)
    if event == "workflow_dispatch":
        target = os.environ.get("DEPLOY_TARGET", "all")
        if target not in {"all", "frontend", "backend"}:
            raise ValueError("Unknown Koji deployment target")
        if target == "frontend":
            changes["backend"] = False
        if target == "backend":
            changes["frontend"] = False
        if os.environ.get("FORCE_MODEL_DEPLOY", "").lower() == "true":
            changes["models"] = True
    changes.update(test_targets(paths, changes))
    output = "".join(f"{name}={str(value).lower()}\n" for name, value in changes.items())
    print(output, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
            handle.write(output)


if __name__ == "__main__":
    main()
