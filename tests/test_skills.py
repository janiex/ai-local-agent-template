"""Skill-level tests. These run against a throwaway git repo, no LLM needed."""
from __future__ import annotations

import subprocess

import pytest

from ai_agent_template.skills.registry import all_skills, get_skill, registered_names


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A tiny git repo with two commits on two branches."""
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "t@example.com"], tmp_path)
    _git(["config", "user.name", "Tester"], tmp_path)
    (tmp_path / "a.txt").write_text("hello\n")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "first"], tmp_path)
    _git(["checkout", "-b", "feature"], tmp_path)
    (tmp_path / "a.txt").write_text("hello\nworld\n")
    _git(["commit", "-am", "second"], tmp_path)
    _git(["checkout", "main"], tmp_path)
    return tmp_path


def test_builtin_skills_registered():
    assert "git_stats" in registered_names()
    assert "github_diff" in registered_names()
    assert {s.name for s in all_skills()} >= {"git_stats", "github_diff"}


def test_git_stats(repo):
    result = get_skill("git_stats").run(path=str(repo))
    assert result.ok
    assert result.data["total_commits"] == 1  # main has one commit
    assert "Tester" in "".join(result.data["contributors"])


def test_git_stats_rejects_non_repo(tmp_path):
    result = get_skill("git_stats").run(path=str(tmp_path / "nope"))
    assert not result.ok


def test_local_diff(repo):
    result = get_skill("github_diff").run(path=str(repo), base="main", head="feature")
    assert result.ok
    assert result.data["added"] == 1
    assert "a.txt" in result.data["files"]


def test_missing_required_param_raises():
    # github_diff has no required params, so craft one via validate directly.
    skill = get_skill("git_stats")
    skill.parameters = {**skill.parameters, "path": {"required": True, "type": "string"}}
    with pytest.raises(ValueError):
        skill.validate({})
