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
    .pip_install(
        "requests>=2.32.0",
        "psycopg2-binary>=2.9.9",
        "sentence-transformers>=3.2.0",
    )
    .add_local_python_source("shared")
    .add_local_file("agents/prompt-agent/SKILL.md", PACKAGED_SKILL_PATH)
)
app = modal.App("skill-evolution", image=image)


def _run() -> dict:
    from pathlib import Path
    import shutil
    from shared.skill_evolution import run_automatic_evolution
    from shared.feedback_learning import backfill_preference_pair_embeddings, consolidate_feedback_candidates

    feedback_candidates = []
    feedback_warning = None
    embedding_backfill = {"requested": 0, "completed": 0, "errors": []}
    try:
        embedding_backfill = backfill_preference_pair_embeddings(
            int(os.getenv("FEEDBACK_EMBEDDING_BACKFILL_LIMIT", "200"))
        )
        feedback_candidates = consolidate_feedback_candidates(
            memento_min_pairs=int(os.getenv("MEMENTO_MIN_PAIRS", "10")),
            skill_min_pairs=int(os.getenv("AGENT_SKILL_MIN_PAIRS", "25")),
            minimum_sessions=int(os.getenv("MEMORY_MIN_SESSIONS", "3")),
            minimum_users=int(os.getenv("MEMORY_MIN_USERS", "3")),
        )
    except Exception as exc:
        # Keep the established prompt-skill evolution job available during a
        # rolling migration where the new feedback tables may not exist yet.
        feedback_warning = f"feedback consolidation skipped: {exc}"

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
    return {
        **result,
        "feedback_memory_candidates": len(feedback_candidates),
        "feedback_warning": feedback_warning,
        "embedding_backfill": embedding_backfill,
    }


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


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("agent-urls-secret"),
        modal.Secret.from_name("supabase-secret"),
    ],
    volumes={SKILLS_VOLUME_PATH: skills_vol},
    timeout=60,
)
def approve_skill_version(version: int) -> dict:
    """Human-triggered deploy of a reviewed candidate onto the live skills-vol Volume.

    Review candidates first with `python scripts/manage_skill_versions.py show <version>`,
    then run: modal run agents/skill-generator/modal_app.py::approve_skill_version --version N
    """
    from pathlib import Path
    from shared.skill_evolution import approve_and_deploy_skill_version

    return approve_and_deploy_skill_version(
        Path(SKILL_DIRECTORY), version, deployment_callback=skills_vol.commit
    )
