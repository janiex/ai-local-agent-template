"""The Skill abstraction.

A *skill* is a single capability the agent can invoke — like a tool/function.
Keeping skills small, declarative, and self-describing is what lets the agent
loop present them to any LLM (local or external) and lets the project grow by
simply dropping a new skill folder into the `skills/` directory.

Skills follow the Anthropic Agent Skills layout: each skill is a directory under
`skills/` containing a `SKILL.md` (YAML frontmatter metadata + docs) and a
`skill.py` (this `Skill` subclass). The loader reads the frontmatter and applies
`name`, `description`, `version`, `license`, and `metadata` to the class, so the
implementation here only declares the executable `parameters` and `run`.

To add a skill, see `skills/<name>/SKILL.md` for the metadata contract and the
README's "Add a skill" section.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SkillResult:
    """Outcome of a skill invocation, fed back to the agent as an observation."""

    ok: bool
    output: str
    data: Dict[str, Any] = field(default_factory=dict)

    def as_observation(self) -> str:
        status = "OK" if self.ok else "ERROR"
        return f"[{status}] {self.output}"


class Skill(ABC):
    # --- metadata, normally populated by the loader from SKILL.md ---------
    # A short, unique, machine-friendly name (e.g. "git-stats").
    name: str = ""
    # One line telling the LLM what the skill does and when to use it.
    description: str = ""
    # Semantic version of the skill, from SKILL.md frontmatter.
    version: str = ""
    # SPDX license identifier, from SKILL.md frontmatter.
    license: str = ""
    # Free-form extra metadata (author, category, requires, ...).
    metadata: Dict[str, Any] = {}

    # --- execution contract, declared on the implementation class --------
    # JSON-schema-style parameter map: {param: {"type", "description", "required"}}.
    parameters: Dict[str, Dict[str, Any]] = {}

    @abstractmethod
    def run(self, **kwargs: Any) -> SkillResult:
        """Execute the skill. Must not raise for *expected* failures — return
        a SkillResult(ok=False, ...) instead, so the agent can recover."""
        raise NotImplementedError

    # ---- helpers shared by all skills ------------------------------------
    def validate(self, kwargs: Dict[str, Any]) -> None:
        """Raise ValueError if a required parameter is missing."""
        missing = [
            p
            for p, spec in self.parameters.items()
            if spec.get("required") and kwargs.get(p) in (None, "")
        ]
        if missing:
            raise ValueError(
                f"Skill '{self.name}' missing required parameter(s): {', '.join(missing)}"
            )

    def spec(self) -> Dict[str, Any]:
        """Serializable description used to build the agent's tool catalog."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "license": self.license,
            "metadata": self.metadata,
            "parameters": self.parameters,
        }
