"""Review and transition pgvector-backed agent memory candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shared.db import list_agent_memories, transition_agent_memory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status", choices=["proposed", "approved", "rejected", "deployed", "superseded"])
    list_parser.add_argument("--limit", type=int, default=100)

    transition_parser = subparsers.add_parser("transition")
    transition_parser.add_argument("memory_id")
    transition_parser.add_argument("status", choices=["approved", "rejected", "deployed", "superseded"])

    args = parser.parse_args()
    if args.command == "list":
        result = list_agent_memories(args.status, args.limit)
    else:
        result = transition_agent_memory(args.memory_id, args.status)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
