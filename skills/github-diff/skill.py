"""Implementation for the `github-diff` skill.

Metadata lives in this skill's `SKILL.md`; the loader applies it to this class
at registration time. Here we declare the parameter schema and `run` behaviour.
"""
from __future__ import annotations

from typing import Any, List

from ai_agent_template.skills._run import have, run
from ai_agent_template.skills.base import Skill, SkillResult


class GitHubDiffSkill(Skill):
    parameters = {
        "pr": {
            "type": "integer",
            "description": "GitHub pull request number to fetch the diff for.",
            "required": False,
        },
        "repo": {
            "type": "string",
            "description": "owner/name for the PR (optional; defaults to the repo at `path`).",
            "required": False,
        },
        "base": {
            "type": "string",
            "description": "Base ref for a local diff (e.g. 'main'). Used when `pr` is absent.",
            "required": False,
        },
        "head": {
            "type": "string",
            "description": "Head ref for a local diff (e.g. 'HEAD' or a branch). Used when `pr` is absent.",
            "required": False,
        },
        "path": {
            "type": "string",
            "description": "Repository path for local diffs / default PR repo (default current dir).",
            "required": False,
        },
        "max_lines": {
            "type": "integer",
            "description": "Truncate the diff to this many lines (default 400).",
            "required": False,
        },
    }

    def run(self, **kwargs: Any) -> SkillResult:
        self.validate(kwargs)
        path = str(kwargs.get("path") or ".")
        max_lines = int(kwargs.get("max_lines") or 400)
        pr = self._as_pr_number(kwargs.get("pr"))

        if pr is not None:
            return self._pr_diff(pr, kwargs.get("repo"), path, max_lines)
        return self._local_diff(
            str(kwargs.get("base") or "main"),
            str(kwargs.get("head") or "HEAD"),
            path,
            max_lines,
        )

    @staticmethod
    def _as_pr_number(value: Any):
        """Return a positive PR number, or None.

        Models often pass 0 / "" / "0" as a "no PR" placeholder, so anything that
        is not a positive integer means "fall back to a local ref diff".
        """
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    # ---- GitHub PR diff via gh CLI ---------------------------------------
    def _pr_diff(self, pr, repo, path, max_lines) -> SkillResult:
        if not have("gh"):
            return SkillResult(
                False,
                "GitHub CLI `gh` is not installed. Install it (https://cli.github.com) "
                "or use base/head for a local diff instead.",
            )
        args = ["gh", "pr", "diff", str(pr)]
        if repo:
            args += ["--repo", str(repo)]
        code, out, err = run(args, cwd=path, timeout=60)
        if code != 0:
            return SkillResult(False, f"gh pr diff failed: {err or out}")
        return self._format(out, max_lines, source=f"PR #{pr}")

    # ---- Local diff between refs -----------------------------------------
    def _local_diff(self, base, head, path, max_lines) -> SkillResult:
        if not have("git"):
            return SkillResult(False, "git is not installed or not on PATH.")
        code, _, err = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
        if code != 0:
            return SkillResult(False, f"Not a git repository at {path!r}: {err}")
        code, out, err = run(["git", "diff", f"{base}...{head}"], cwd=path, timeout=60)
        if code != 0:
            return SkillResult(False, f"git diff failed: {err or out}")
        return self._format(out, max_lines, source=f"{base}...{head}")

    # ---- shared formatting -----------------------------------------------
    @staticmethod
    def _format(diff: str, max_lines: int, source: str) -> SkillResult:
        if not diff.strip():
            return SkillResult(True, f"No changes found for {source}.", data={"source": source})
        lines: List[str] = diff.splitlines()
        files = [ln[6:] for ln in lines if ln.startswith("+++ b/")]
        added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))

        body = lines[:max_lines]
        if len(lines) > max_lines:
            body.append(f"... [truncated {len(lines) - max_lines} more lines]")

        summary = (
            f"Diff for {source}: {len(files)} file(s), "
            f"+{added} / -{removed} lines\n\n" + "\n".join(body)
        )
        return SkillResult(
            True,
            summary,
            data={"source": source, "files": files, "added": added, "removed": removed},
        )
