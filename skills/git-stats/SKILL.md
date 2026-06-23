---
name: git-stats
description: >-
  Report statistics about a local git repository — total commits, contributors,
  recent activity, and the most-changed files. Use this when the user asks about
  a repository's history, activity level, contributor breakdown, or which files
  change most often. Read-only; never modifies the repository.
version: 1.0.0
license: MIT
metadata:
  author: ai-agent-template
  category: git
  read_only: true
  requires:
    - git
  entrypoint: skill.py
---

# Git Stats

## Overview
Summarizes the history of a local git repository into a compact, human-readable
report plus structured `data` the agent can reason over.

## When to use
- "How active has this repo been lately?"
- "Who are the top contributors?"
- "Which files change the most?"
- Any question about repository history or health.

Do **not** use it to view code changes — use the `github-diff` skill for diffs.

## Parameters
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | no | Path to the git repository. Defaults to the current directory. |
| `since` | string | no | Git date filter, e.g. `"2 weeks ago"` or `"2026-01-01"`. Scopes all counts. |
| `top_files` | integer | no | How many most-changed files to list. Default `5`. |

## Output
A report containing the repository path, total commit count, contributor list,
the top most-changed files, and the 10 most recent commits. The structured
`data` payload includes `total_commits`, `contributors`, and `top_changed_files`.

## Safety
Read-only. Shells out only to inspection commands (`git rev-list`, `git shortlog`,
`git log`) via an argument list — never a shell string — so caller-supplied
values cannot inject shell syntax.
