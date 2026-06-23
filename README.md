# ai-agent-template

A minimal, **extensible template** for building LLM agents that use *skills*
(tools). It ships with one agent — `GitAgent` — and two skills:

- **`git_stats`** — repository statistics from local git history (commits, contributors, hot files, recent activity).
- **`github_diff`** — a code diff from a GitHub pull request (via the `gh` CLI) or between two local git refs.

The same agent runs against either a **local LLM (Ollama)** or an **external
LLM by API (Anthropic Claude)** — you choose at runtime. The codebase is laid
out so you can add new skills and new agents by dropping in a single file each.

---

## Why it's structured this way

```
ai-agent-template/
├── ai_agent_template/
│   ├── config.py            # env/.env settings (import-light)
│   ├── cli.py               # `ai-agent run | list | health`
│   ├── llm/                 # swappable LLM backends
│   │   ├── base.py          #   LLMProvider ABC (stream + complete)
│   │   ├── factory.py       #   get_provider("ollama" | "anthropic")
│   │   ├── ollama_provider.py
│   │   └── anthropic_provider.py
│   ├── skills/              # capabilities the agent can call
│   │   ├── base.py          #   Skill ABC + SkillResult
│   │   ├── registry.py      #   @register decorator + discovery
│   │   ├── git_stats.py
│   │   └── github_diff.py
│   └── agents/              # agents bundle skills + a persona
│       ├── base.py          #   Agent: the reason→act→observe loop
│       └── git_agent.py     #   the reference agent
└── tests/                   # fast tests, no network/LLM required
```

Three small abstractions keep the parts decoupled:

| Layer | Contract | Add one by… |
|-------|----------|-------------|
| **LLMProvider** | `stream(system, messages)` → text; `complete` derived | subclass + wire into `factory.get_provider` |
| **Skill** | `run(**args)` → `SkillResult`; self-describing `parameters` | subclass + `@register` |
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

### Add a skill

Create `ai_agent_template/skills/my_skill.py`:

```python
from .base import Skill, SkillResult
from .registry import register

@register
class MySkill(Skill):
    name = "my_skill"
    description = "What it does and when the agent should use it."
    parameters = {
        "query": {"type": "string", "description": "...", "required": True},
    }

    def run(self, **kwargs) -> SkillResult:
        self.validate(kwargs)
        return SkillResult(ok=True, output="...", data={})
```

Import it in `skills/__init__.py` (one line) so it registers, then add its
name to an agent's `SKILL_NAMES`. Return `SkillResult(ok=False, ...)` for
expected failures so the agent can recover instead of crashing.

### Add an agent

Copy `agents/git_agent.py`, set `name`, `persona`, and `SKILL_NAMES`, then
register it in `agents/__init__.py`:

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
