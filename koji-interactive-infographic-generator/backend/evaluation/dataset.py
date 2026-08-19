"""Deterministic 100-prompt evaluation dataset across five subjects and three levels."""

from __future__ import annotations

from typing import Any

TOPICS = {
    "biology": [
        "parts of a plant cell", "photosynthesis", "human digestive system", "food chain",
        "DNA structure", "mitosis", "heart blood flow", "respiratory system", "neuron signaling",
        "ecosystem energy pyramid", "flower pollination", "kidney filtration", "immune response",
        "protein synthesis", "natural selection", "water transport in plants", "enzyme action",
        "chromosome inheritance", "bacterial cell structure", "carbon cycle in an ecosystem",
    ],
    "physics": [
        "Newton's laws of motion", "simple electric circuit", "reflection of light", "sound waves",
        "states of matter", "forces on an inclined plane", "electromagnetic spectrum", "projectile motion",
        "series and parallel circuits", "heat transfer", "lever mechanics", "wave interference",
        "magnetic field around a wire", "energy conservation", "pressure in fluids", "lens ray diagram",
        "momentum collision", "uniform circular motion", "transformer operation", "radioactive decay",
    ],
    "chemistry": [
        "water molecule structure", "periodic table groups", "acid-base neutralization", "atom structure",
        "ionic bonding", "covalent bonding", "balancing a chemical equation", "reaction energy profile",
        "electrolysis", "distillation apparatus", "metal reactivity series", "gas particle model",
        "redox reaction", "molar concentration", "organic functional groups", "polymer formation",
        "equilibrium shift", "titration setup", "crystal lattice", "catalyst reaction pathway",
    ],
    "mathematics": [
        "fraction equivalence", "area and perimeter", "coordinate plane", "triangle angle sum",
        "Pythagorean theorem", "linear equation graph", "quadratic function", "circle geometry",
        "probability tree", "ratio and proportion", "integer number line", "transformation geometry",
        "trigonometric ratios", "exponential growth", "derivative as slope", "integral as area",
        "vector addition", "normal distribution", "matrix transformation", "geometric sequence",
    ],
    "earth_science": [
        "layers of Earth", "water cycle", "rock cycle", "solar system", "plate tectonics",
        "volcano structure", "earthquake waves", "weather fronts", "cloud formation", "ocean currents",
        "phases of the Moon", "seasons on Earth", "greenhouse effect", "soil horizons", "fossil formation",
        "river erosion", "groundwater aquifer", "atmospheric layers", "star life cycle", "climate feedback loops",
    ],
}

GRADE_LEVELS = ("elementary", "middle", "high")
GRADE_TEXT = {
    "elementary": "grades 3-5",
    "middle": "grades 6-8",
    "high": "grades 9-12",
}


def build_dataset() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for subject, topics in TOPICS.items():
        for index, topic in enumerate(topics):
            grade = GRADE_LEVELS[index % len(GRADE_LEVELS)]
            records.append({
                "prompt_id": f"{subject}-{index + 1:02d}",
                "subject": subject,
                "grade_level": grade,
                "prompt": (
                    f"Create a clear educational infographic about {topic} for {GRADE_TEXT[grade]}. "
                    "Use accurate labels and show the most important relationships."
                ),
            })
    if len(records) != 100:
        raise AssertionError(f"Evaluation dataset must contain 100 prompts, found {len(records)}")
    return records

