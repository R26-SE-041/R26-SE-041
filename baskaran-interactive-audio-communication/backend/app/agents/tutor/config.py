"""Safe loader for the Tutor Agent's Markdown configuration."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)
_CONFIG_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TutorConfig:
    skills: str
    persona: str
    memento: str


def _read_required_markdown(filename: str) -> str:
    path = _CONFIG_DIR / filename
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(
            f"Tutor configuration file unavailable: {filename} ({type(exc).__name__})"
        ) from exc
    if not content:
        raise RuntimeError(f"Tutor configuration file is empty: {filename}")
    logger.info("Tutor configuration loaded: %s", filename)
    return content


@lru_cache(maxsize=1)
def load_tutor_config() -> TutorConfig:
    """Load and validate all three Tutor configuration documents."""
    config = TutorConfig(
        skills=_read_required_markdown("skills.md"),
        persona=_read_required_markdown("persona.md"),
        memento=_read_required_markdown("memento.md"),
    )
    logger.info("Tutor configuration loaded successfully")
    return config


@lru_cache(maxsize=1)
def load_tutor_instructions() -> str:
    """Return shared Tutor guidance for both base and fine-tuned routes."""
    config = load_tutor_config()
    return "\n\n".join((config.skills, config.persona, "Memento policy:\n" + config.memento))
