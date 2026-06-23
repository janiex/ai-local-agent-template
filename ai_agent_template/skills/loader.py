"""Discover skills from the dedicated `skills/` directory (Anthropic layout).

A skill can take one of three forms, all discovered automatically:

  1. Folder + Python   : `skills/<name>/SKILL.md` + `skills/<name>/skill.py`
                         (a `Skill` subclass with custom `run` logic).
  2. Folder + markdown : `skills/<name>/SKILL.md` whose frontmatter declares an
                         `execution` command — no Python needed.
  3. Single markdown   : `skills/<name>.md` with an `execution` command — the
                         simplest way to add a skill: just drop in one file.

The loader is the single source of truth for *metadata*: it reads the
frontmatter and stamps `name`/`description`/`version`/`license`/`metadata` onto
the skill class, then registers it. For declarative skills it also builds the
executable class (see `command_skill.CommandSkill`) from the `execution` block,
so docs and behaviour live in one place.
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
from .command_skill import CommandSkill

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
        if entry.is_dir():
            md = entry / "SKILL.md"
            if not md.exists():
                continue
            label = f"folder {entry.name!r}"
            expected_name = entry.name
        elif entry.suffix == ".md" and entry.name != "README.md":
            if not entry.read_text(encoding="utf-8").lstrip().startswith("---"):
                continue  # a plain markdown note, not a skill
            md = entry
            label = f"file {entry.name!r}"
            expected_name = entry.stem
        else:
            continue

        meta, _docs = parse_skill_md(md)
        name = meta["name"]
        if name in registry.registered_names(_ensure=False):
            continue
        if expected_name != name:
            raise ValueError(
                f"Skill {label} does not match its declared name {name!r}."
            )

        cls = _build_skill_class(entry, meta, name)

        # Frontmatter is canonical for metadata; stamp it onto the class.
        cls.name = name
        cls.description = meta["description"].strip()
        cls.version = str(meta.get("version", ""))
        cls.license = str(meta.get("license", ""))
        cls.metadata = meta.get("metadata", {}) or {}

        registry.add(cls)
        newly.append(name)

    return newly


def _build_skill_class(entry: Path, meta: Dict[str, Any], name: str) -> Type[Skill]:
    """Return the Skill class for a discovered entry.

    A `skill.py` (Python) takes precedence; otherwise an `execution` block in the
    frontmatter yields a declarative `CommandSkill`.
    """
    if entry.is_dir():
        impl_path = entry / str(meta.get("metadata", {}).get("entrypoint", "skill.py"))
        if impl_path.exists():
            return _load_impl_class(impl_path, name)

    if meta.get("execution"):
        return _build_command_class(meta, name)

    raise ValueError(
        f"Skill {name!r} has neither a skill.py implementation nor an "
        f"'execution' block in its frontmatter."
    )


def _build_command_class(meta: Dict[str, Any], name: str) -> Type[CommandSkill]:
    """Create a CommandSkill subclass configured from the `execution` block."""
    spec = meta.get("execution") or {}
    command = spec.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError(
            f"Skill {name!r}: execution.command must be a non-empty list of argv tokens."
        )
    attrs: Dict[str, Any] = {
        "parameters": meta.get("parameters", {}) or {},
        "command": [str(tok) for tok in command],
        "cwd_template": str(spec.get("cwd", ".")),
        "requires": [str(r) for r in (spec.get("requires") or [])],
        "timeout": int(spec.get("timeout", 30)),
        "max_output_lines": int(spec.get("max_output_lines", 200)),
    }
    return type(f"CommandSkill_{name.replace('-', '_')}", (CommandSkill,), attrs)


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
