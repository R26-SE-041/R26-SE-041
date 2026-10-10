"""Review SKILL.md evolution candidates. Deploying one requires Modal Volume
access, so this script only lists/shows candidates from Postgres; run the
printed `modal run` command to actually deploy an approved version."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shared.db import get_skill_version, list_skill_versions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status", choices=["candidate", "rejected", "deployed", "superseded"])
    list_parser.add_argument("--limit", type=int, default=20)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("version", type=int)

    args = parser.parse_args()
    if args.command == "list":
        result = list_skill_versions(args.status, args.limit)
    else:
        result = get_skill_version(args.version)
        if result is None:
            print(f"No skill version {args.version}", file=sys.stderr)
            return 1
        if result["status"] == "candidate":
            print(
                "To deploy this candidate, run:\n"
                f"  modal run agents/skill-generator/modal_app.py::approve_skill_version --version {args.version}",
                file=sys.stderr,
            )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
