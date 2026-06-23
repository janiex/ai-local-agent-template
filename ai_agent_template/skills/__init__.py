"""Built-in skills.

Importing this package registers every built-in skill (via the `@register`
decorator on each class). New skill modules added here are picked up
automatically as long as they are imported below.
"""
from __future__ import annotations

from .base import Skill, SkillResult
from .registry import all_skills, get_skill, register, registered_names

# Import skill modules for their registration side effects.
from . import git_stats  # noqa: F401,E402
from . import github_diff  # noqa: F401,E402

__all__ = [
    "Skill",
    "SkillResult",
    "register",
    "get_skill",
    "all_skills",
    "registered_names",
]
