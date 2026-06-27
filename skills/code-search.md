---
name: code-search
description: >-
  Search a git repository's tracked files for a text pattern and return matching
  files with line numbers. Use when the user asks where something is defined,
  used, or mentioned in the code. Read-only.
version: 1.0.0
metadata:
  category: git
  read_only: true
parameters:
  pattern:
    type: string
    description: Text or regex to search for.
    required: true
  path:
    type: string
    description: Repository path.
    required: false
    default: "."
execution:
  command: ["git", "-C", "{path}", "grep", "-n", "-I", "--", "{pattern}"]
  requires: ["git"]
  max_output_lines: 80
---
# Code Search