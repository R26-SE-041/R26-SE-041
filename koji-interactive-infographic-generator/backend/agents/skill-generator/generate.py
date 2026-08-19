"""Manual entry point for validation-gated SKILL.md evolution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shared.skill_evolution import run_automatic_evolution


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, default=BACKEND_DIR / "skills")
    parser.add_argument("--minimum-experiences", type=int, default=50)
    parser.add_argument("--validation-prompts", type=int, default=10)
    parser.add_argument("--minimum-improvement", type=float, default=0.10)
    args = parser.parse_args()
    result = run_automatic_evolution(
        args.skill_dir,
        minimum_experiences=args.minimum_experiences,
        validation_prompt_count=args.validation_prompts,
        minimum_improvement=args.minimum_improvement,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

