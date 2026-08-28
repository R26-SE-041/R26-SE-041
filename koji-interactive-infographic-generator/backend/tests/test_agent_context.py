from pathlib import Path

from shared.memory import MemoryManager


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_static_context_has_stable_authority_order(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    global_root = tmp_path / "global"
    _write(global_root / "PERSONA.md", "shared persona")
    _write(global_root / "SKILL.md", "global policy")
    _write(global_root / "MEMENTO.md", "global lesson")
    _write(agents_root / "eval-agent" / "PERSONA.md", "strict evaluator persona")
    _write(agents_root / "eval-agent" / "SKILL.md", "evaluation skill")
    _write(agents_root / "eval-agent" / "MEMENTO.md", "evaluation lesson")

    context = MemoryManager(
        agent_name="eval-agent",
        agents_root=agents_root,
        global_root=global_root,
    ).load_static_context()

    system_context = context["system_context"]
    expected_system = [
        "shared persona",
        "strict evaluator persona",
        "global policy",
        "evaluation skill",
    ]
    assert all(value in system_context for value in expected_system)
    assert [system_context.index(value) for value in expected_system] == sorted(
        system_context.index(value) for value in expected_system
    )
    assert "global lesson" not in system_context
    assert "evaluation lesson" not in system_context
    assert "global lesson" in context["memento"]
    assert "evaluation lesson" in context["memento"]


def test_static_context_never_loads_another_agents_files(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    global_root = tmp_path / "global"
    _write(agents_root / "prompt-agent" / "SKILL.md", "prompt-only rule")
    _write(agents_root / "prompt-agent" / "PERSONA.md", "prompt-only persona")
    _write(agents_root / "image-agent" / "SKILL.md", "image-only rule")
    _write(agents_root / "image-agent" / "PERSONA.md", "image-only persona")

    context = MemoryManager(
        agent_name="image-agent",
        agents_root=agents_root,
        global_root=global_root,
    ).load_static_context()

    assert "image-only rule" in context["system_context"]
    assert "image-only persona" in context["system_context"]
    assert "prompt-only rule" not in context["system_context"]
    assert "prompt-only persona" not in context["system_context"]
