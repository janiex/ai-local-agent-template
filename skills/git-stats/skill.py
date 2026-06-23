"""Implementation for the `git-stats` skill.

Metadata (name, description, version, license, ...) lives in this skill's
`SKILL.md`; the loader applies it to this class at registration time. Here we
only declare the executable parameter schema and the `run` behaviour.
"""
from __future__ import annotations

from typing import Any

from ai_agent_template.skills._run import have, run
from ai_agent_template.skills.base import Skill, SkillResult


class GitStatsSkill(Skill):
    parameters = {
        "path": {
            "type": "string",
            "description": "Path to the git repository (defaults to current dir).",
            "required": False,
        },
        "since": {
            "type": "string",
            "description": "Optional git date filter, e.g. '2 weeks ago' or '2026-01-01'.",
            "required": False,
        },
        "top_files": {
            "type": "integer",
            "description": "How many most-changed files to list (default 5).",
            "required": False,
        },
    }

    def run(self, **kwargs: Any) -> SkillResult:
        self.validate(kwargs)
        path = str(kwargs.get("path") or ".")
        since = kwargs.get("since")
        top_files = int(kwargs.get("top_files") or 5)

        if not have("git"):
            return SkillResult(False, "git is not installed or not on PATH.")

        # Confirm it's a repository first; gives a clean error otherwise.
        code, _, err = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
        if code != 0:
            return SkillResult(False, f"Not a git repository at {path!r}: {err}")

        log_range = ["--since", since] if since else []

        total = self._count(["git", "rev-list", "--count", "HEAD", *log_range], path)
        contributors = self._lines(
            ["git", "shortlog", "-sne", "--all", *log_range], path
        )
        recent = self._lines(
            ["git", "log", "--pretty=format:%h %ad %an: %s", "--date=short",
             "-n", "10", *log_range],
            path,
        )
        changed = self._top_changed(path, log_range, top_files)

        scope = f" since {since!r}" if since else ""
        report = "\n".join(
            [
                f"Repository: {path}",
                f"Total commits{scope}: {total}",
                f"Contributors: {len(contributors)}",
                *(f"  - {c}" for c in contributors[:10]),
                "",
                f"Top {top_files} most-changed files:",
                *(f"  {n:>4}  {f}" for n, f in changed),
                "",
                "Recent commits:",
                *(f"  {line}" for line in recent),
            ]
        )
        return SkillResult(
            True,
            report,
            data={
                "path": path,
                "total_commits": total,
                "contributors": contributors,
                "top_changed_files": changed,
            },
        )

    # ---- internals -------------------------------------------------------
    @staticmethod
    def _count(args, cwd) -> int:
        code, out, _ = run(args, cwd=cwd)
        try:
            return int(out) if code == 0 and out else 0
        except ValueError:
            return 0

    @staticmethod
    def _lines(args, cwd):
        code, out, _ = run(args, cwd=cwd)
        return [ln for ln in out.splitlines() if ln.strip()] if code == 0 else []

    def _top_changed(self, cwd, log_range, n):
        # Count how often each file appears in commit diffs.
        code, out, _ = run(
            ["git", "log", "--pretty=format:", "--name-only", *log_range], cwd=cwd
        )
        if code != 0:
            return []
        counts: dict[str, int] = {}
        for line in out.splitlines():
            line = line.strip()
            if line:
                counts[line] = counts.get(line, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:n]
        return [(cnt, f) for f, cnt in ranked]
