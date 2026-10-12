"""Classify Koji deployment changes without triggering other components."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

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


def main() -> None:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    force = event == "workflow_dispatch" or os.environ.get("GITHUB_REF", "").startswith("refs/tags/")
    before = os.environ.get("BEFORE_SHA", "")
    after = os.environ["GITHUB_SHA"]
    if event == "pull_request":
        before = os.environ["PR_BASE_SHA"]
        after = os.environ["PR_HEAD_SHA"]
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
    output = "".join(f"{name}={str(value).lower()}\n" for name, value in changes.items())
    print(output, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
            handle.write(output)


if __name__ == "__main__":
    main()
