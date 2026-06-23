"""A fully declarative skill — defined by markdown alone, no Python.

A skill's markdown frontmatter can carry an `execution` block instead of a
`skill.py`:

    parameters:
      path: {type: string, required: false, default: "."}
      count: {type: integer, required: false, default: 15}
    execution:
      command: ["git", "-C", "{path}", "log", "--oneline", "-n", "{count}"]
      requires: ["git"]
      timeout: 20
      max_output_lines: 100

The loader builds a `CommandSkill` subclass from that block. At run time it
substitutes `{param}` placeholders into the argv list and runs it via the safe
subprocess helper (an argument *list*, never a shell), so a new skill can be
introduced by dropping in a single markdown file.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ._run import have, run
from .base import Skill, SkillResult


class CommandSkill(Skill):
    # All of these are populated by the loader from the `execution` frontmatter.
    command: List[str] = []
    cwd_template: str = "."
    requires: List[str] = []
    timeout: int = 30
    max_output_lines: int = 200

    def run(self, **kwargs: Any) -> SkillResult:
        params = self._with_defaults(kwargs)
        self.validate(params)

        for tool in self.requires:
            if not have(tool):
                return SkillResult(
                    False, f"required command {tool!r} is not installed or not on PATH."
                )

        argv = [self._subst(token, params) for token in self.command]
        cwd = self._subst(self.cwd_template, params) or "."

        code, out, err = run(argv, cwd=cwd, timeout=self.timeout)
        if code != 0:
            return SkillResult(
                False, f"`{' '.join(argv)}` failed (exit {code}): {err or out}".strip()
            )

        lines = out.splitlines()
        if len(lines) > self.max_output_lines:
            dropped = len(lines) - self.max_output_lines
            lines = lines[: self.max_output_lines] + [f"... [truncated {dropped} more lines]"]
        body = "\n".join(lines) if lines else "(command produced no output)"
        return SkillResult(True, body, data={"command": argv, "exit_code": code})

    # ---- helpers ---------------------------------------------------------
    def _with_defaults(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Start from declared defaults, then overlay caller-supplied values."""
        params: Dict[str, Any] = {
            name: spec["default"]
            for name, spec in self.parameters.items()
            if "default" in spec
        }
        params.update({k: v for k, v in kwargs.items() if v is not None})
        return params

    @staticmethod
    def _subst(token: str, params: Dict[str, Any]) -> str:
        out = str(token)
        for key, value in params.items():
            out = out.replace("{" + key + "}", str(value))
        return out
