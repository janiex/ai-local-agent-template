"""Skill-level tests. These run against a throwaway git repo, no LLM needed."""
from __future__ import annotations

import subprocess

import pytest

from ai_agent_template.skills.registry import all_skills, get_skill, registered_names
from ai_agent_template.skills.loader import parse_skill_md, skills_dir


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


def test_skills_discovered_from_directory():
    # Skills are loaded from the dedicated `skills/` folder via their SKILL.md.
    assert "git-stats" in registered_names()
    assert "github-diff" in registered_names()
    assert {s.name for s in all_skills()} >= {"git-stats", "github-diff"}


def test_metadata_applied_from_skill_md():
    skill = get_skill("git-stats")
    assert skill.description  # populated from SKILL.md
    assert skill.version == "1.0.0"
    assert skill.license == "MIT"
    assert skill.metadata.get("read_only") is True


def test_skill_md_frontmatter_parses():
    meta, body = parse_skill_md(skills_dir() / "git-stats" / "SKILL.md")
    assert meta["name"] == "git-stats"
    assert "git" in meta["metadata"]["requires"]
    assert body  # the human-readable docs section is non-empty


def test_git_stats(repo):
    result = get_skill("git-stats").run(path=str(repo))
    assert result.ok
    assert result.data["total_commits"] == 1  # main has one commit
    assert "Tester" in "".join(result.data["contributors"])


def test_git_stats_rejects_non_repo(tmp_path):
    result = get_skill("git-stats").run(path=str(tmp_path / "nope"))
    assert not result.ok


def test_local_diff(repo):
    result = get_skill("github-diff").run(path=str(repo), base="main", head="feature")
    assert result.ok
    assert result.data["added"] == 1
    assert "a.txt" in result.data["files"]


def test_missing_required_param_raises():
    skill = get_skill("git-stats")
    skill.parameters = {**skill.parameters, "path": {"required": True, "type": "string"}}
    with pytest.raises(ValueError):
        skill.validate({})
