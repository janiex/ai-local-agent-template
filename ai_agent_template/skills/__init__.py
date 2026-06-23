"""Skills subsystem.

Skills live in the dedicated top-level `skills/` directory (Anthropic Agent
Skills layout): one folder per skill, each with a `SKILL.md` (metadata + docs)
and a `skill.py` (the `Skill` subclass). They are discovered lazily on first
access via `registry`/`loader` — importing this package has no side effects.
"""
from __future__ import annotations

from .base import Skill, SkillResult
from .loader import load_skills, skills_dir
from .registry import all_skills, get_skill, register, registered_names

__all__ = [
    "Skill",
    "SkillResult",
    "register",
    "get_skill",
    "all_skills",
    "registered_names",
    "load_skills",
    "skills_dir",
]
