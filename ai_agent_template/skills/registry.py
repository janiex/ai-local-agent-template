"""Registry of available skills, populated by discovery from `skills/`.

The registry lazily triggers the filesystem loader on first access, so callers
just use `get_skill`, `all_skills`, or `registered_names` without worrying about
when discovery happens.

For a skill defined *in code* (rather than as a SKILL.md folder), use the
`register` decorator — handy for tests and quick experiments.
"""
from __future__ import annotations

from typing import Dict, List, Type

from .base import Skill

_REGISTRY: Dict[str, Type[Skill]] = {}
_loaded = False


def add(cls: Type[Skill]) -> Type[Skill]:
    """Add a Skill subclass to the registry by its `name`."""
    if not getattr(cls, "name", ""):
        raise ValueError(f"{cls.__name__} must have a non-empty `name`.")
    if cls.name in _REGISTRY and _REGISTRY[cls.name] is not cls:
        raise ValueError(f"Duplicate skill name: {cls.name!r}")
    _REGISTRY[cls.name] = cls
    return cls


# `register` is the in-code decorator alias for `add`.
register = add


def _ensure_loaded() -> None:
    """Run filesystem discovery exactly once."""
    global _loaded
    if _loaded:
        return
    _loaded = True  # set first so the loader's imports can't recurse forever
    from .loader import load_skills

    load_skills()


def get_skill(name: str) -> Skill:
    _ensure_loaded()
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise KeyError(
            f"Unknown skill {name!r}. Registered: {sorted(_REGISTRY)}"
        ) from None


def all_skills() -> List[Skill]:
    _ensure_loaded()
    return [cls() for cls in _REGISTRY.values()]


def registered_names(_ensure: bool = True) -> List[str]:
    if _ensure:
        _ensure_loaded()
    return sorted(_REGISTRY)
