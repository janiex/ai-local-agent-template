---
name: github-diff
description: >-
  Show a code diff. Given a GitHub pull request number, fetch that PR's diff via
  the GitHub CLI (`gh`); otherwise diff two local git refs (base...head). Use
  this when the user wants to review what changed in a pull request, branch, or
  between two commits. Read-only; never modifies the repository or the remote.
version: 1.0.0
license: MIT
metadata:
  author: ai-agent-template
  category: git
  read_only: true
  requires:
    - git
    - gh
  entrypoint: skill.py
---

# GitHub Diff

## Overview
Returns a unified diff together with a summary (files touched, lines added /
removed). Prefers the GitHub CLI for PR diffs because it handles authentication,
forks, and private repositories; falls back to a local `git diff` so the skill
remains useful offline.

## When to use
- "What changed in PR #42?"
- "Diff my feature branch against main."
- Reviewing changes between two commits or refs.

For repository history or activity, use the `git-stats` skill instead.

## Parameters
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pr` | integer | no | GitHub pull request number. When given, the PR diff is fetched via `gh`. |
| `repo` | string | no | `owner/name` for the PR. Defaults to the repo at `path`. |
| `base` | string | no | Base ref for a local diff (e.g. `main`). Used when `pr` is absent. |
| `head` | string | no | Head ref for a local diff (e.g. `HEAD`). Used when `pr` is absent. |
| `path` | string | no | Repository path for local diffs / default PR repo. Default: current dir. |
| `max_lines` | integer | no | Truncate the diff to this many lines. Default `400`. |

## Output
A summary line (`source`, file count, `+added / -removed`) followed by the
(optionally truncated) diff body. The structured `data` payload includes
`source`, `files`, `added`, and `removed`.

## Safety
Read-only. Uses only `gh pr diff` and `git diff`, invoked with an argument list
(never a shell string). Performs no pushes, commits, or remote writes.
