"""Agent-scoped, tiered memory facade used by the orchestration pipeline.

Memory is intentionally split by lifetime:
  * ``WorkingMemory`` is request-local and must never be persisted implicitly.
  * ``SKILL.md`` is stable procedural/semantic memory.
  * ``MEMENTO.md`` is small, human-reviewed durable memory for one agent.
  * database experiences are episodic memory retrieved only when relevant.

Keeping these tiers separate prevents one agent's instructions or experiences from
silently leaking into another agent's prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


_AGENT_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class WorkingMemory:
    raw_prompt: str
    agent_name: str = "prompt-agent"
    retry_count: int = 0
    retry_feedback: str | None = None
    best_attempt: dict[str, Any] | None = None
    assembled_context: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)


class MemoryManager:
    """Coordinate one agent's working, semantic, durable, and episodic memory.

    ``skill_path`` remains supported for older callers. New code should pass an
    ``agent_name`` and let the manager resolve files from ``backend/agents``.
    """

    def __init__(
        self,
        skill_path: str | Path | None = None,
        *,
        agent_name: str = "prompt-agent",
        agents_root: str | Path | None = None,
        persona_path: str | Path | None = None,
        memento_path: str | Path | None = None,
        global_root: str | Path | None = None,
    ) -> None:
        if not _AGENT_NAME.fullmatch(agent_name):
            raise ValueError(f"Invalid agent name: {agent_name!r}")

        backend_root = Path(__file__).resolve().parents[1]
        self.agent_name = agent_name
        self.agents_root = Path(agents_root) if agents_root else backend_root / "agents"
        self.global_root = Path(global_root) if global_root else backend_root / "config" / "global"
        agent_root = self.agents_root / agent_name
        preferred_skill = agent_root / "SKILL.md"
        legacy_skill = backend_root / "skills" / "SKILL.md"

        if skill_path:
            self.skill_path = Path(skill_path)
        elif preferred_skill.exists():
            self.skill_path = preferred_skill
        elif agent_name == "prompt-agent":
            self.skill_path = legacy_skill
        else:
            self.skill_path = preferred_skill
        self.persona_path = Path(persona_path) if persona_path else agent_root / "PERSONA.md"
        self.memento_path = Path(memento_path) if memento_path else agent_root / "MEMENTO.md"

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return ""

    def load_semantic_memory(self) -> str:
        return self._read(self.skill_path)

    def load_memento_memory(self) -> str:
        """Load this agent's reviewed durable notes, never another agent's."""
        return self._read(self.memento_path)

    def load_system_persona(self) -> str:
        """Load global and agent-local personas without crossing agent scope."""
        return self._join_scoped(
            "Global persona",
            self._read(self.global_root / "PERSONA.md"),
            "Active agent persona",
            self._read(self.persona_path),
        )

    def load_static_context(self) -> dict[str, str]:
        """Return ordered, scoped context for the common agent prompt pipeline.

        The ordering is deliberate: persona and global policies have higher
        authority than an agent's relevant skill and reviewed lessons. The
        request/query stays request-local and is appended by each caller.
        """
        system_persona = self.load_system_persona()
        global_persona = self._read(self.global_root / "PERSONA.md")
        agent_persona = self._read(self.persona_path)
        global_skill = self._read(self.global_root / "SKILL.md")
        global_memento = self._read(self.global_root / "MEMENTO.md")
        local_skill = self.load_semantic_memory()
        local_memento = self.load_memento_memory()
        policy_and_skill = self._join_scoped(
            "Global policies",
            global_skill,
            "Relevant agent skill",
            local_skill,
        )
        reviewed_lessons = self._join_scoped(
            "Global lessons",
            global_memento,
            "Agent lessons",
            local_memento,
        )
        return {
            "system_persona": system_persona,
            "global_persona": global_persona,
            "agent_persona": agent_persona,
            "global_skill_rules": global_skill,
            "agent_skill_rules": local_skill,
            "global_memento": global_memento,
            "agent_memento": local_memento,
            # Backward-compatible keys used by the deployed agents.
            "skill_rules": policy_and_skill,
            "memento": reviewed_lessons,
            "system_context": self._join_blocks(
                "System persona",
                system_persona,
                policy_and_skill,
            ),
        }

    @staticmethod
    def _join_blocks(label: str, first: str, *blocks: str) -> str:
        rendered = [f"## {label}\n{first}"] if first else []
        rendered.extend(block.strip() for block in blocks if block.strip())
        return "\n\n".join(rendered)

    @staticmethod
    def _join_scoped(first_label: str, first: str, second_label: str, second: str) -> str:
        blocks = []
        if first:
            blocks.append(f"## {first_label}\n{first}")
        if second:
            blocks.append(f"## {second_label}\n{second}")
        return "\n\n".join(blocks)

    def recall(self, raw_prompt: str, limit: int = 3) -> list[dict[str, Any]]:
        if not raw_prompt.strip() or limit < 1:
            return []
        # The current episodic table stores prompt-enhancement successes. Other
        # agents keep isolated static memory until they get an agent-specific
        # experience schema and promotion/evaluation policy.
        if self.agent_name != "prompt-agent":
            return []
        from shared.db import get_similar_experiences
        from shared.rag import embed
        return get_similar_experiences(raw_prompt, embed(raw_prompt), min(limit, 5))

    def recall_scoped(
        self,
        query: str,
        *,
        user_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve deployed vector memories without crossing user or agent scope."""
        clean = query.strip()
        if not clean or limit < 1:
            return []
        from shared.db import retrieve_scoped_memories
        from shared.rag import embed
        return retrieve_scoped_memories(
            query_embedding=embed(clean),
            agent_name=self.agent_name,
            user_id=user_id,
            limit=min(limit, 10),
        )

    def promote(
        self,
        raw_prompt: str,
        enhanced_prompt: str,
        visual_score: float,
        pedagogical_score: float,
        **metadata: Any,
    ) -> str | None:
        if self.agent_name != "prompt-agent":
            return None
        if min(visual_score, pedagogical_score) < 7.0:
            return None
        from shared.db import insert_prompt_experience
        from shared.rag import embed
        return insert_prompt_experience(
            raw_prompt=raw_prompt,
            enhanced_prompt=enhanced_prompt,
            visual_score=visual_score,
            pedagogical_score=pedagogical_score,
            prompt_embedding=embed(raw_prompt),
            clip_score=metadata.get("clip_score"),
            vlm_feedback=metadata.get("vlm_feedback"),
            subject_tag=metadata.get("subject_tag"),
            grade_tag=metadata.get("grade_tag"),
            style_tag=metadata.get("style_tag"),
            skill_version=metadata.get("skill_version"),
        )

    def consolidate(self, similarity_threshold: float = 0.90) -> dict[str, int]:
        from shared.db import consolidate_prompt_experiences
        return consolidate_prompt_experiences(similarity_threshold)
