"""Discover skills from the dedicated `skills/` directory (Anthropic layout).

Each skill is a folder containing:
  - SKILL.md   : YAML frontmatter (name, description, version, license, metadata)
                 plus human-readable docs.
  - skill.py   : a single `Skill` subclass implementing `run` + `parameters`.

The loader is the single source of truth for *metadata*: it reads the
frontmatter and stamps `name`/`description`/`version`/`license`/`metadata` onto
the implementation class, then registers it. This keeps the docs (SKILL.md) and
the code (skill.py) from drifting apart.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type

import yaml

from ..config import settings
from . import registry
from .base import Skill

_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def skills_dir() -> Path:
    """Where to look for skills: SKILLS_DIR if set, else `<repo root>/skills`."""
    if settings.skills_dir:
        return Path(settings.skills_dir).expanduser().resolve()
    # loader.py -> skills -> ai_agent_template -> <repo root>
    return Path(__file__).resolve().parents[2] / "skills"


def load_skills() -> List[str]:
    """Scan the skills directory and register every well-formed skill.

    Idempotent: skills already in the registry are skipped, so it is safe to
    call more than once. Returns the names that were newly registered.
    """
    root = skills_dir()
    newly: List[str] = []
    if not root.is_dir():
        return newly

    for entry in sorted(root.iterdir()):
        md = entry / "SKILL.md"
        if not entry.is_dir() or not md.exists():
            continue

        meta, _docs = parse_skill_md(md)
        name = meta["name"]
        if name in registry.registered_names(_ensure=False):
            continue

        if entry.name != name:
            raise ValueError(
                f"Skill folder {entry.name!r} does not match SKILL.md name {name!r}."
            )

        impl_path = entry / str(meta.get("metadata", {}).get("entrypoint", "skill.py"))
        cls = _load_impl_class(impl_path, name)

        # Frontmatter is canonical for metadata; stamp it onto the class.
        cls.name = name
        cls.description = meta["description"].strip()
        cls.version = str(meta.get("version", ""))
        cls.license = str(meta.get("license", ""))
        cls.metadata = meta.get("metadata", {}) or {}

        registry.add(cls)
        newly.append(name)

    return newly


def parse_skill_md(path: Path) -> Tuple[Dict[str, Any], str]:
    """Return (frontmatter_dict, docs_body) for a SKILL.md file.

    Validates the required `name` and `description` fields and the name format.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing YAML frontmatter (must start with '---').")

    # Split: ['', '<frontmatter>', '<body>'] on the first two '---' fences.
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: malformed frontmatter (need opening and closing '---').")

    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping.")

    name = meta.get("name")
    desc = meta.get("description")
    if not name or not desc:
        raise ValueError(f"{path}: frontmatter must define both 'name' and 'description'.")
    if not _NAME_RE.match(str(name)):
        raise ValueError(
            f"{path}: name {name!r} must be lowercase letters/digits separated by hyphens."
        )

    return meta, parts[2].strip()


def _load_impl_class(path: Path, name: str) -> Type[Skill]:
    """Import `path` as a module and return its single Skill subclass."""
    if not path.exists():
        raise FileNotFoundError(f"Skill {name!r}: implementation not found at {path}.")

    module_name = f"ai_agent_template._skills.{name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import skill implementation at {path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    candidates = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, Skill) and obj is not Skill
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"Skill {name!r}: expected exactly one Skill subclass in {path}, "
            f"found {len(candidates)}."
        )
    return candidates[0]
