"""Detect and persist recurring interaction-feedback patterns."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shared.feedback_patterns import analyze_and_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--minimum-occurrences", type=int, default=3)
    args = parser.parse_args()
    patterns = analyze_and_store(args.days, args.minimum_occurrences)
    print(json.dumps(patterns, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

