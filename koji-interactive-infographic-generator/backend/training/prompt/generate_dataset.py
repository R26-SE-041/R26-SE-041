"""Generate a deterministic five-organ Qwen SFT dataset from curated knowledge.

No model writes the targets. The anatomy JSON is the sole source of canonical IDs,
which prevents a teacher model from introducing unsupported structures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from anatomy import get_structure, get_view, list_supported_organs, load_organ, validate_anatomy_spec


HERE = Path(__file__).resolve().parent
SYSTEM_PROMPT = (
    "You are EduVision's prompt enhancement agent. Return one JSON object only. "
    "Preserve the user's learning intent and grade level. For supported anatomy, return anatomy_spec only "
    "using supplied canonical IDs and allowed enum values; do not write an image prompt. The application "
    "validator and deterministic builder own the final FLUX prompt. For non-anatomy, return enhanced_prompt "
    "and anatomy_spec with is_anatomy=false."
)
ORGAN_ALIASES = {
    "heart": ["heart", "cardiac organ", "idhayam", "iruthayam"],
    "brain": ["brain", "cerebral anatomy", "moolai"],
    "lungs": ["lungs", "lung anatomy", "pulmonary system", "nuraiyeeral"],
    "liver": ["liver", "hepatic organ", "kalleeral"],
    "kidneys": ["kidneys", "kidney anatomy", "renal organs", "siruneeragam"],
}
GRADES = ["primary_school", "middle_school", "high_school", "undergraduate", "general_audience"]
GRADE_PHRASES = {
    "primary_school": "primary school children",
    "middle_school": "grade 8 students",
    "high_school": "high school biology students",
    "undergraduate": "undergraduate anatomy students",
    "general_audience": "a general educational audience",
}
STYLES = ["clean medical illustration", "textbook-style illustration", "high-clarity educational diagram"]
EMPHASES = [
    "shape", "spatial relationships", "major regions", "orientation", "clear boundaries",
    "learner-friendly detail", "proportion", "internal organization", "external landmarks",
    "functional context", "visual simplicity", "anatomical hierarchy", "recognizable form",
    "standard terminology", "balanced composition", "clinical clarity", "exam revision",
]
SPLIT_COUNTS = {
    "train": {"per_organ": 560, "generic": 800},
    "validation": {"per_organ": 70, "generic": 100},
    "test": {"per_organ": 70, "generic": 100},
}
TEMPLATES = {
    "train": [
        ("standard", "Create a {style} of the human {alias} for {audience}."),
        ("classroom", "I need a classroom visual showing {alias} anatomy to {audience}."),
        ("structure_focus", "Show {structures} in a clear {alias} illustration for {audience}."),
        ("process", "Make an interactive {alias} visual explaining {process} for {audience}."),
        ("concise", "{alias} {view} educational image, {grade}."),
        ("noisy", "pls crete {alias} digram fr {audience}, anatomically corect"),
        ("tanglish", "{audience} kku {alias} parts clear ah kaattura image create pannu"),
        ("constraint", "Generate an isolated {alias} in {view}; keep the image clean and suitable for {audience}."),
    ],
    "validation": [
        ("validation_rephrase", "Design a medically grounded visual lesson about the {alias} for {audience}."),
        ("validation_question", "Can you visualize {structures} of the {alias} so {audience} can understand them?"),
    ],
    "test": [
        ("heldout_natural", "Help me teach {audience} what the inside of the {alias} looks like."),
        ("heldout_noisy", "need accurte {alias} pic {view} no words in pic for {audience}"),
    ],
}
PROCESSES = {
    "heart": "blood flow",
    "brain": "the relationship among major regions",
    "lungs": "air flow through the conducting airways",
    "liver": "blood inflow and bile outflow",
    "kidneys": "urine flow through the collecting system",
}
GENERIC_SUBJECTS = [
    "the water cycle", "photosynthesis", "a volcano", "the solar system", "a food web",
    "plate tectonics", "a simple electric circuit", "the nitrogen cycle", "a plant cell", "DNA replication",
]
GENERIC_TEMPLATES = {
    "train": ["Create an educational illustration of {subject} for {audience}.", "Make a clear classroom visual about {subject} for {audience}.", "pls make {subject} digram for {audience}"],
    "validation": ["Design a teaching image that explains {subject} to {audience}."],
    "test": ["I want a visual lesson on {subject} suitable for {audience}."],
}


def _stable_id(split: str, organ: str, index: int, prompt: str) -> str:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    return f"{split}-{organ}-{index:04d}-{digest}"


def _anatomy_example(split: str, organ: str, index: int, rng: random.Random) -> dict[str, Any]:
    knowledge = load_organ(organ)
    view = get_view(organ, knowledge["views"]["default_view"])
    family, template = TEMPLATES[split][index % len(TEMPLATES[split])]
    required = list(view["required_structures"])
    if family in {"structure_focus", "validation_question"}:
        size = min(len(required), 3 + index % 4)
        required = sorted(rng.sample(required, size))
    grade = GRADES[index % len(GRADES)]
    alias = ORGAN_ALIASES[organ][(index // len(TEMPLATES[split])) % len(ORGAN_ALIASES[organ])]
    labels = [get_structure(organ, value)["label"] for value in required]
    raw_prompt = template.format(
        alias=alias,
        audience=GRADE_PHRASES[grade],
        grade=grade.replace("_", " "),
        process=PROCESSES[organ],
        structures=", ".join(labels[:6]),
        style=STYLES[index % len(STYLES)],
        view=view["label"],
    )
    raw_prompt = f"{raw_prompt} Focus on {EMPHASES[index % len(EMPHASES)]}."
    show_flow = family == "process"
    focus = required if family in {"structure_focus", "validation_question"} else []
    spec = validate_anatomy_spec({
        "is_anatomy": True,
        "organ": organ,
        "view": view["id"],
        "grade_level": grade,
        "required_structures": required,
        "focus_structures": focus,
        "detail_level": {
            "primary_school": "basic",
            "middle_school": "intermediate",
            "high_school": "intermediate",
            "undergraduate": "advanced",
            "general_audience": "intermediate",
        }[grade],
        "orientation": view.get("default_orientation", "portrait"),
        "show_flow": show_flow,
    })
    answer = {"anatomy_spec": spec}
    allowed_ids = sorted(item["id"] for item in knowledge["structures"]["structures"])
    anatomy_system_prompt = (
        f"{SYSTEM_PROMPT} Supported organ: {organ}. Allowed view: {view['id']}. "
        f"Allowed canonical structure IDs: {', '.join(allowed_ids)}. "
        "Allowed grade levels: primary_school, middle_school, high_school, undergraduate, general_audience. "
        "Allowed detail levels: basic, intermediate, advanced. "
        "Allowed orientations: square, portrait, landscape."
    )
    return {
        "id": _stable_id(split, organ, index, raw_prompt),
        "split": split,
        "organ": organ,
        "allowed_structure_ids": allowed_ids,
        "template_family": family,
        "messages": [
            {"role": "system", "content": anatomy_system_prompt},
            {"role": "user", "content": raw_prompt},
            {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False, separators=(",", ":"))},
        ],
    }


def _generic_example(split: str, index: int) -> dict[str, Any]:
    subject = GENERIC_SUBJECTS[index % len(GENERIC_SUBJECTS)]
    grade = GRADES[(index // len(GENERIC_SUBJECTS)) % len(GRADES)]
    templates = GENERIC_TEMPLATES[split]
    template = templates[index % len(templates)]
    raw_prompt = template.format(subject=subject, audience=GRADE_PHRASES[grade])
    variation = index // (len(GENERIC_SUBJECTS) * len(GRADES) * len(templates))
    if variation:
        raw_prompt = f"{raw_prompt} Composition variation {variation + 1}: emphasize clear visual hierarchy."
    answer = {
        "enhanced_prompt": (
            f"A clear, accurate {STYLES[index % len(STYLES)]} explaining {subject}, suitable for "
            f"{GRADE_PHRASES[grade]}, balanced composition, readable visual hierarchy, and a clean background."
        ),
        "anatomy_spec": {"is_anatomy": False},
    }
    return {
        "id": _stable_id(split, "generic", index, raw_prompt),
        "split": split,
        "organ": None,
        "template_family": f"generic_{split}",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_prompt},
            {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False, separators=(",", ":"))},
        ],
    }


def _validate(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    prompt_sets: dict[str, set[str]] = {}
    family_sets: dict[str, set[str]] = {}
    counts: dict[str, Any] = {}
    for split, rows in rows_by_split.items():
        ids = [row["id"] for row in rows]
        prompts = [row["messages"][1]["content"] for row in rows]
        if len(ids) != len(set(ids)) or len(prompts) != len(set(prompts)):
            raise ValueError(f"{split}: duplicate IDs or prompts")
        for row in rows:
            answer = json.loads(row["messages"][2]["content"])
            validate_anatomy_spec(answer["anatomy_spec"])
        prompt_sets[split] = set(prompts)
        family_sets[split] = {row["template_family"] for row in rows}
        counts[split] = {"total": len(rows), "by_organ": dict(Counter(str(row["organ"] or "generic") for row in rows))}
    split_names = list(rows_by_split)
    for index, left in enumerate(split_names):
        for right in split_names[index + 1:]:
            if prompt_sets[left] & prompt_sets[right]:
                raise ValueError(f"Prompt leakage between {left} and {right}")
            if family_sets[left] & family_sets[right]:
                raise ValueError(f"Template-family leakage between {left} and {right}")
    return counts


def generate(output_dir: Path, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    organs = list_supported_organs()
    if organs != ["brain", "heart", "kidneys", "liver", "lungs"]:
        raise ValueError(f"Expected exactly five supported organs, got {organs}")
    rows_by_split: dict[str, list[dict[str, Any]]] = {}
    for split, requested in SPLIT_COUNTS.items():
        rows = [
            _anatomy_example(split, organ, index, rng)
            for organ in organs
            for index in range(requested["per_organ"])
        ]
        rows.extend(_generic_example(split, index) for index in range(requested["generic"]))
        rng.shuffle(rows)
        rows_by_split[split] = rows
    counts = _validate(rows_by_split)
    output_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for split, rows in rows_by_split.items():
        path = output_dir / f"{split}.jsonl"
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        path.write_text(content, encoding="utf-8", newline="\n")
        hashes[path.name] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = {
        "dataset": "eduvision-five-organ-prompt-sft",
        "version": "2.0.0",
        "seed": seed,
        "organs": organs,
        "counts": counts,
        "sha256": hashes,
        "target_model": "Qwen/Qwen2.5-3B-Instruct",
        "leakage_policy": "Prompts and template families are disjoint across train, validation, and test.",
        "output_contract": "Anatomy requests return anatomy_spec only; deterministic application code builds FLUX prompts.",
        "target_provenance": "Deterministically generated from versioned curated anatomy JSON; no teacher-model targets.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE / "data")
    parser.add_argument("--seed", type=int, default=26041)
    args = parser.parse_args()
    print(json.dumps(generate(args.output_dir, args.seed), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
