# ai-agent-template

A minimal, **extensible template** for building LLM agents that use *skills*
(tools). It ships with one agent — `GitAgent` — and two skills:

- **`git_stats`** — repository statistics from local git history (commits, contributors, hot files, recent activity).
- **`github_diff`** — a code diff from a GitHub pull request (via the `gh` CLI) or between two local git refs.

The same agent runs against either a **local LLM (Ollama)** or an **external
LLM by API (Anthropic Claude)** — you choose at runtime. The codebase is laid
out so you can add new skills and new agents by dropping in a single file each.

> 📖 For a complete, code-referenced walkthrough of how everything fits together
> — the request lifecycle, each component, and experiments per layer — see
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Why it's structured this way

```
ai-agent-template/
├── skills/                  # dedicated skills dir (Anthropic Agent Skills layout)
│   ├── git-log.md           #   a declarative skill — markdown only, no code
│   ├── git-stats/
│   │   ├── SKILL.md         #   metadata (name, description, ...) + docs
│   │   └── skill.py         #   a coded skill: Skill subclass with run()
│   └── github-diff/
│       ├── SKILL.md
│       └── skill.py
├── ai_agent_template/
│   ├── config.py            # env/.env settings (import-light)
│   ├── cli.py               # `ai-agent run | list | health`
│   ├── llm/                 # swappable LLM backends
│   │   ├── base.py          #   LLMProvider ABC (stream + complete)
│   │   ├── factory.py       #   get_provider("ollama" | "anthropic")
│   │   ├── ollama_provider.py
│   │   └── anthropic_provider.py
│   ├── skills/              # the skills *framework* (not the skills themselves)
│   │   ├── base.py          #   Skill ABC + SkillResult
│   │   ├── command_skill.py #   CommandSkill: runs a declarative argv template
│   │   ├── loader.py        #   discovers skills, reads frontmatter
│   │   ├── registry.py      #   lazy discovery + lookup
│   │   └── _run.py          #   safe subprocess helper
│   └── agents/              # agents bundle skills + a persona
│       ├── base.py          #   Agent: the reason→act→observe loop
│       └── git_agent.py     #   the reference agent
└── tests/                   # fast tests, no network/LLM required
```

Skills follow the **[Anthropic Agent Skills](https://www.anthropic.com/news/skills)
layout** and come in two flavours, both discovered automatically from `skills/`:

- **Declarative (no code):** a single markdown file `skills/<name>.md` (or a
  folder with `SKILL.md`) whose frontmatter declares a parameter schema and an
  `execution.command`. The loader builds a runnable skill from it. This is the
  fastest way to add one — **drop in a file, done.**
- **Coded:** a folder `skills/<name>/` with `SKILL.md` (metadata) + `skill.py`
  (a `Skill` subclass) for logic too complex for a single command.

Either way the frontmatter is the single source of truth for metadata (`name`,
`description`, `version`, `license`, `metadata`), so docs and behaviour can't
drift apart.

Three small abstractions keep the parts decoupled:

| Layer | Contract | Add one by… |
|-------|----------|-------------|
| **LLMProvider** | `stream(system, messages)` → text; `complete` derived | subclass + wire into `factory.get_provider` |
| **Skill** | a markdown file's frontmatter (declarative) **or** a `skill.py` `Skill` subclass (coded) | drop a `.md` (or folder) into `skills/` |
| **Agent** | inherits the loop; declares which skills + persona | subclass `Agent` + add to `agents.AGENTS` |

The agent talks to the LLM with a **provider-agnostic JSON protocol** (a
ReAct-style reason→act→observe loop) rather than provider-native tool calling,
so the identical agent works on a small local model *and* on Claude.

---

## Quickstart

```bash
cd ai-agent-template
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # or: pip install -r requirements.txt
cp .env.example .env             # then edit
```

### Use a local LLM (default)

Install [Ollama](https://ollama.com), then:

```bash
ollama pull llama3.1
# .env: LLM_PROVIDER=ollama
ai-agent health
ai-agent run "How active is the repo at ../ over the last month?"
```

### Use the external Claude API

```bash
pip install -e ".[anthropic]"
# .env: LLM_PROVIDER=anthropic  and  ANTHROPIC_API_KEY=sk-ant-...
ai-agent run --provider anthropic "Summarize what changed in PR #7"
```

### Commands

```bash
ai-agent list                      # show agents, skills, providers
ai-agent health [--provider ...]   # check the LLM backend is reachable
ai-agent run "<task>" [--agent git] [--provider ollama|anthropic] [-v]
```

`-v` prints each step's skill call and observation to stderr; the final answer
goes to stdout.

---

## Extending the template

### Add a skill — no code (declarative)

Drop **one markdown file** into `skills/`. It's discovered on the next run; you
don't touch any Python. Create `skills/my-skill.md`:

```markdown
---
name: my-skill                  # required; must match the file name
description: >-                  # required; shown to the LLM, so state WHEN to use it
  What it does and when the agent should reach for it.
version: 1.0.0
license: MIT
metadata:
  category: git                 # GitAgent uses every skill with category: git
  read_only: true
parameters:
  path:
    type: string
    description: Path to the repository.
    required: false
    default: "."
execution:
  command: ["git", "-C", "{path}", "status", "--short"]  # argv; {param} placeholders
  requires: ["git"]             # commands that must be on PATH
  timeout: 20
  max_output_lines: 100
---

# My Skill
Free-form docs go here.
```

`{path}` is substituted into the argv list **as a single argument** — never
through a shell — so values can't inject extra commands. Any parameter used in
the command should be `required` or have a `default`. See
[`skills/git-log.md`](skills/git-log.md) for a working example.

Because `GitAgent` selects skills by `metadata.category`, a new `category: git`
skill is immediately usable — **no agent code changes**.

### Add a skill — with code

When a single command isn't enough, use a folder with custom logic. Create
`skills/my-skill/SKILL.md` (same frontmatter, minus `execution`) plus
`skills/my-skill/skill.py`:

```python
from ai_agent_template.skills.base import Skill, SkillResult

class MySkill(Skill):                         # metadata comes from SKILL.md
    parameters = {
        "query": {"type": "string", "description": "...", "required": True},
    }

    def run(self, **kwargs) -> SkillResult:
        self.validate(kwargs)
        return SkillResult(ok=True, output="...", data={})
```

Return `SkillResult(ok=False, ...)` for expected failures so the agent can
recover instead of crashing.

> Skills are discovered from the project's top-level `skills/` directory by
> default. Point `SKILLS_DIR` at another path to load skills from elsewhere.

### Add an agent

Copy `agents/git_agent.py`, set `name`, `persona`, and how it selects skills
(by `CATEGORY`, or pass an explicit `skills=[...]`), then register it in
`agents/__init__.py`:

```python
AGENTS = {"git": GitAgent, "myagent": MyAgent}
```

It's now runnable: `ai-agent run --agent myagent "..."`.

### Add an LLM backend

Subclass `LLMProvider`, implement `stream`, and add a branch to
`factory.get_provider`. Everything above it is unchanged.

---

## Design notes

- **Safety:** skills that shell out use an argument *list* (never `shell=True`),
  so LLM-supplied values can't inject shell syntax. See `skills/_run.py`.
- **Resilience:** the agent tolerates non-JSON replies (common with small local
  models) by nudging the model to retry, and enforces a `max_steps` budget.
- **Lazy deps:** the `anthropic` SDK is imported only when that backend is used,
  so local-only setups need nothing extra.

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

Tests use a scripted fake LLM and a throwaway git repo — fast and offline.
The same suite runs in CI on push/PR — see [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Put it on GitHub

The repo is already initialized with an initial commit. To publish:

```bash
# with the GitHub CLI:
gh repo create ai-agent-template --public --source=. --remote=origin --push

# or manually, after creating an empty repo on github.com:
git remote add origin git@github.com:<you>/ai-agent-template.git
git push -u origin main
```

## License

MIT — see [LICENSE](LICENSE).
