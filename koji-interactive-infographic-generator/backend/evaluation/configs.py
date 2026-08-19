"""Conference ablation configurations."""

from __future__ import annotations

CONFIGS = {
    "B0": {"enable_reflexion": False, "enable_memento": False, "enable_skill_rules": False, "enable_dual_critic": False},
    "B1": {"enable_reflexion": False, "enable_memento": False, "enable_skill_rules": False, "enable_dual_critic": True},
    "B2": {"enable_reflexion": True, "enable_memento": False, "enable_skill_rules": False, "enable_dual_critic": True},
    "B3": {"enable_reflexion": False, "enable_memento": True, "enable_skill_rules": False, "enable_dual_critic": True},
    "B5": {"enable_reflexion": False, "enable_memento": False, "enable_skill_rules": True, "enable_dual_critic": True},
    "E": {"enable_reflexion": True, "enable_memento": True, "enable_skill_rules": True, "enable_dual_critic": True},
}

DESCRIPTIONS = {
    "B0": "Vanilla linear pipeline; aggregate score retained only for legacy comparison",
    "B1": "Dual critic only",
    "B2": "Dual critic plus Reflexion",
    "B3": "Dual critic plus Memento",
    "B5": "Dual critic plus SKILL.md",
    "E": "Full generation pipeline",
}
