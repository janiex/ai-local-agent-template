"""A tiny registry so skills self-register and agents can discover them.

Usage:
    from .registry import register

    @register
    class MySkill(Skill):
        name = "my_skill"
        ...

Then `all_skills()` returns one instance of every registered skill. Importing
`ai_agent_template.skills` triggers registration of the built-in skills.
"""
from __future__ import annotations

from typing import Dict, List, Type

from .base import Skill

_REGISTRY: Dict[str, Type[Skill]] = {}


def register(cls: Type[Skill]) -> Type[Skill]:
    """Class decorator: add a Skill subclass to the registry by its `name`."""
    if not getattr(cls, "name", ""):
        raise ValueError(f"{cls.__name__} must define a non-empty `name`.")
    if cls.name in _REGISTRY and _REGISTRY[cls.name] is not cls:
        raise ValueError(f"Duplicate skill name: {cls.name!r}")
    _REGISTRY[cls.name] = cls
    return cls


def get_skill(name: str) -> Skill:
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise KeyError(
            f"Unknown skill {name!r}. Registered: {sorted(_REGISTRY)}"
        ) from None


def all_skills() -> List[Skill]:
    return [cls() for cls in _REGISTRY.values()]


def registered_names() -> List[str]:
    return sorted(_REGISTRY)
