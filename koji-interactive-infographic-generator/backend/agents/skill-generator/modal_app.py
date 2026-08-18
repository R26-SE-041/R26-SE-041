"""Scheduled Modal job for feedback analysis and validated SKILL deployment."""

from __future__ import annotations

import os

import modal

SKILLS_VOLUME_PATH = "/root/skills"
SKILL_DIRECTORY = f"{SKILLS_VOLUME_PATH}/prompt-agent"
PACKAGED_SKILL_PATH = "/root/agent-config/prompt-agent/SKILL.md"

skills_vol = modal.Volume.from_name("skills-vol", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("requests>=2.32.0", "psycopg2-binary>=2.9.9")
    .add_local_python_source("shared")
    .add_local_file("agents/prompt-agent/SKILL.md", PACKAGED_SKILL_PATH)
)
app = modal.App("skill-evolution", image=image)


def _run() -> dict:
    from pathlib import Path
    import shutil
    from shared.skill_evolution import run_automatic_evolution

    skill_directory = Path(SKILL_DIRECTORY)
    skill_directory.mkdir(parents=True, exist_ok=True)
    skill_path = skill_directory / "SKILL.md"
    if not skill_path.exists():
        shutil.copyfile(PACKAGED_SKILL_PATH, skill_path)
        skills_vol.commit()

    result = run_automatic_evolution(
        skill_directory,
        minimum_experiences=int(os.getenv("SKILL_MIN_EXPERIENCES", "50")),
        validation_prompt_count=int(os.getenv("SKILL_VALIDATION_PROMPTS", "10")),
        minimum_improvement=float(os.getenv("SKILL_MIN_IMPROVEMENT", "0.10")),
        deployment_callback=skills_vol.commit,
    )
    return result


@app.function(
    image=image,
    schedule=modal.Cron("0 2 * * 0"),
    secrets=[
        modal.Secret.from_name("agent-urls-secret"),
        modal.Secret.from_name("supabase-secret"),
    ],
    volumes={SKILLS_VOLUME_PATH: skills_vol},
    timeout=21_600,
    max_containers=1,
)
def scheduled_evolution() -> dict:
    """Run every Sunday at 02:00 UTC."""
    return _run()


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("agent-urls-secret"),
        modal.Secret.from_name("supabase-secret"),
    ],
    volumes={SKILLS_VOLUME_PATH: skills_vol},
    timeout=21_600,
    max_containers=1,
)
def run_now() -> dict:
    """Manually trigger the same guarded workflow."""
    return _run()
