"""Fast integrity and leakage checks for the generated prompt SFT dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from anatomy import list_supported_organs, load_organ, validate_anatomy_spec


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_number}: invalid JSON") from exc
            rows.append(row)
    return rows


def validate(data_dir: Path) -> dict[str, Any]:
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    known: dict[str, dict[str, Any]] = {}
    for organ in list_supported_organs():
        bundle = load_organ(organ)
        known[organ] = {
            "ids": {item["id"] for item in bundle["structures"]["structures"]},
            "views": {item["id"] for item in bundle["views"]["views"]},
            "trigger": bundle["structures"].get("trigger_word"),
        }
    prompt_sets: dict[str, set[str]] = {}
    family_sets: dict[str, set[str]] = {}
    observed_counts: dict[str, Any] = {}
    for split in ("train", "validation", "test"):
        path = data_dir / f"{split}.jsonl"
        content = path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != manifest["sha256"][path.name]:
            raise ValueError(f"{path.name}: SHA-256 mismatch")
        rows = _read_rows(path)
        ids: set[str] = set()
        prompts: set[str] = set()
        families: set[str] = set()
        counts: Counter[str] = Counter()
        for row in rows:
            if row.get("split") != split:
                raise ValueError(f"{row.get('id')}: incorrect split")
            if row["id"] in ids:
                raise ValueError(f"{split}: duplicate ID {row['id']}")
            ids.add(row["id"])
            messages = row.get("messages") or []
            if [item.get("role") for item in messages] != ["system", "user", "assistant"]:
                raise ValueError(f"{row['id']}: invalid chat roles")
            prompt = str(messages[1].get("content") or "")
            if not prompt or prompt in prompts:
                raise ValueError(f"{split}: empty or duplicate prompt")
            prompts.add(prompt)
            families.add(str(row.get("template_family") or ""))
            answer = json.loads(messages[2]["content"])
            spec = answer.get("anatomy_spec") or {}
            organ = row.get("organ")
            counts[str(organ or "generic")] += 1
            if organ is None:
                if spec != {"is_anatomy": False}:
                    raise ValueError(f"{row['id']}: generic target was routed to anatomy")
                continue
            if set(answer) != {"anatomy_spec"}:
                raise ValueError(f"{row['id']}: anatomy target must contain anatomy_spec only")
            if organ not in known or spec.get("organ") != organ or not spec.get("is_anatomy"):
                raise ValueError(f"{row['id']}: organ mismatch")
            if set(row.get("allowed_structure_ids") or []) != known[organ]["ids"]:
                raise ValueError(f"{row['id']}: canonical vocabulary mismatch")
            if spec.get("view") not in known[organ]["views"]:
                raise ValueError(f"{row['id']}: unknown view")
            required = spec.get("required_structures") or []
            if not required or not set(required).issubset(known[organ]["ids"]):
                raise ValueError(f"{row['id']}: non-canonical structures")
            if validate_anatomy_spec(spec) != spec:
                raise ValueError(f"{row['id']}: anatomy target is not normalized")
        prompt_sets[split] = prompts
        family_sets[split] = families
        observed_counts[split] = {"total": len(rows), "by_organ": dict(counts)}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if prompt_sets[left] & prompt_sets[right]:
            raise ValueError(f"Prompt leakage between {left} and {right}")
        if family_sets[left] & family_sets[right]:
            raise ValueError(f"Template leakage between {left} and {right}")
    if observed_counts != manifest["counts"]:
        raise ValueError("Manifest counts do not match dataset")
    return {"status": "ok", "counts": observed_counts, "sha256": manifest["sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    args = parser.parse_args()
    print(json.dumps(validate(args.data_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
