---
name: git-log
description: >-
  List the most recent commits of a local git repository, one line per commit
  (short hash, date, author, subject). Use when the user wants to see recent
  commit history or commit messages. Read-only; never modifies the repository.
version: 1.0.0
license: MIT
metadata:
  author: ai-agent-template
  category: git
  read_only: true
parameters:
  path:
    type: string
    description: Path to the git repository.
    required: false
    default: "."
  count:
    type: integer
    description: How many recent commits to list.
    required: false
    default: 15
execution:
  command: ["git", "-C", "{path}", "log", "--pretty=format:%h %ad %an: %s", "--date=short", "-n", "{count}"]
  requires: ["git"]
  timeout: 20
  max_output_lines: 100
---

# Git Log

A **declarative skill** — there is no `skill.py`. Everything the agent needs is
in the frontmatter above: the parameter schema and an `execution.command` whose
`{path}` and `{count}` placeholders are filled in safely (as argv tokens, never
a shell string) before the command runs.

## When to use
- "Show me the last 10 commits."
- "What are the recent commit messages?"

## Adding your own
Copy this file to `skills/<your-name>.md`, change the frontmatter `name` (it
must match the file name), adjust `parameters` and `execution.command`, and the
skill is live on the next run — no code changes.
