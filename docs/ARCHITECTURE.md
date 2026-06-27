# ai-agent-template — Architecture & Usage

A complete, code-referenced guide to how the system works, plus experiments you
can run against each layer. File links are relative to the repository root.

## 1. The mental model

The system is a small **agent loop** that turns a natural-language task into a
sequence of **skill** (tool) calls, driven by an **LLM** that can be either local
(Ollama) or remote (Anthropic). Three abstractions are deliberately decoupled so
each can change without touching the others:

```
        ┌──────────────┐     picks a skill each turn      ┌──────────────┐
 task → │    Agent     │ ───────────────────────────────► │     LLM      │
        │  (the loop)  │ ◄─────────────────────────────── │  (provider)  │
        └──────┬───────┘     returns one JSON action      └──────────────┘
               │ dispatches
               ▼
        ┌──────────────┐
        │    Skill     │  (git-stats, github-diff, git-log, code-search, …)
        │  run()→result│  discovered from the skills/ directory
        └──────────────┘
```

The agent never calls the model's "native" tool API. Instead it uses a
**provider-agnostic JSON protocol** (see `_SYSTEM_TEMPLATE` in
[ai_agent_template/agents/base.py](../ai_agent_template/agents/base.py)), so the
identical agent works on a small local model *and* on Claude.

## 2. Directory layout

```
ai-agent-template/
├── skills/                       ← the skills themselves (data, not framework)
│   ├── code-search.md            #   declarative skill (one markdown file)
│   ├── git-log.md                #   declarative skill
│   ├── git-stats/{SKILL.md,skill.py}    #   coded skill
│   └── github-diff/{SKILL.md,skill.py}  #   coded skill
├── ai_agent_template/            ← the framework (Python package)
│   ├── config.py                 #   settings from env/.env
│   ├── cli.py                    #   `ai-agent run | list | health`
│   ├── llm/                      #   provider abstraction + backends
│   ├── skills/                   #   Skill base, loader, registry, CommandSkill, _run
│   └── agents/                   #   Agent loop + GitAgent
├── tests/                        ← pytest suite (offline)
├── .github/workflows/ci.yml      ← runs pytest on push/PR (py 3.9/3.11/3.12)
└── pyproject.toml / requirements.txt / .env.example / LICENSE
```

Key idea: **`skills/` is content, `ai_agent_template/skills/` is the engine.**
You add capability by dropping files in the former, never editing the latter.

## 3. End-to-end request lifecycle

Tracing `ai-agent run "where is CommandSkill defined?" -v`:

1. **CLI parse** — [cli.py](../ai_agent_template/cli.py) `build_parser` reads the
   task, `--agent` (default `git`), `--provider`, `-v`.
2. **Build agent** — `_build_agent` → `get_provider(None)` (reads `LLM_PROVIDER`
   from `.env`) → `GitAgent(provider)`.
3. **Skill discovery** — constructing `GitAgent` calls `all_skills()`, which
   lazily triggers the loader to scan `skills/` and register every skill
   (`_ensure_loaded` in [registry.py](../ai_agent_template/skills/registry.py)).
4. **Agent selects skills** — `GitAgent._discover()` keeps only skills whose
   `metadata.category == "git"`
   ([git_agent.py](../ai_agent_template/agents/git_agent.py)). `code-search`
   qualifies, so it's in the toolset.
5. **Loop turn 1** — `Agent.run` builds a system prompt listing the skills and
   asks the model for one JSON action
   ([base.py](../ai_agent_template/agents/base.py)). The model replies, e.g.
   `{"thought":"search the code","action":"code-search","args":{"pattern":"class CommandSkill"}}`.
6. **Dispatch** — `_dispatch` looks up the `code-search` skill and calls
   `run(pattern="class CommandSkill")`.
7. **Skill executes** — `CommandSkill.run` substitutes the args into `git grep`
   and runs it safely, returning a `SkillResult`.
8. **Observation fed back** — the result becomes an `Observation:` message; the
   loop repeats.
9. **Finalize** — when the model returns `{"action":"final","answer":"..."}`,
   `run` returns an `AgentResult`. The CLI prints `answer` to stdout; with `-v`,
   each step's call + observation went to stderr (`_cmd_run` in
   [cli.py](../ai_agent_template/cli.py)).

## 4. Component deep-dive

### 4.1 Configuration — `config.py`

A single import-light `Settings` dataclass loads everything from
environment/`.env` ([config.py](../ai_agent_template/config.py)):
`llm_provider`, `ollama_host`, `ollama_model`, `anthropic_api_key`,
`anthropic_model`, `agent_max_steps`, and `skills_dir`. It imports only stdlib +
`python-dotenv`, so it's safe to import from tests and the CLI without pulling
heavy dependencies.

**Experiment:**
```bash
python -c "from ai_agent_template.config import settings; print(settings)"
```

### 4.2 LLM layer — `llm/`

The contract is one method ([llm/base.py](../ai_agent_template/llm/base.py)):

```python
class LLMProvider(ABC):
    def stream(self, system, messages) -> Iterator[str]: ...   # abstract
    def complete(self, system, messages) -> str:               # derived: "".join(stream)
    def health_check(self) -> str: ...
```

- `complete()` is what the agent loop uses; it's auto-derived from `stream()`,
  so a new backend only implements streaming.
- `factory.get_provider(name)`
  ([llm/factory.py](../ai_agent_template/llm/factory.py)) maps
  `"ollama"`/`"anthropic"` to a backend, importing each **lazily** (so
  Ollama-only users never need the `anthropic` package). Precedence: explicit
  argument > `.env`.
- `OllamaProvider`
  ([llm/ollama_provider.py](../ai_agent_template/llm/ollama_provider.py)) POSTs
  to `/api/chat` with `stream=True`; `health_check` verifies the model is pulled.
- `AnthropicProvider`
  ([llm/anthropic_provider.py](../ai_agent_template/llm/anthropic_provider.py))
  uses `messages.stream`.

**Experiment (no agent, raw model):**
```bash
ai-agent health
python -c "
from ai_agent_template.llm.factory import get_provider
p = get_provider('ollama')
print(p.complete('You are terse.', [{'role':'user','content':'Say hi in 3 words.'}]))"
```

### 4.3 Skills subsystem — `ai_agent_template/skills/`

**`Skill` base** ([skills/base.py](../ai_agent_template/skills/base.py)) holds
metadata fields (`name`, `description`, `version`, `license`, `metadata`)
**populated by the loader from frontmatter**, plus the execution contract
(`parameters`, `run()`), `validate()` (enforces required params), and
`SkillResult` (carries `ok`, `output`, `data`; `as_observation()` formats
`[OK]`/`[ERROR]`).

**`_run.py`** ([skills/_run.py](../ai_agent_template/skills/_run.py)) is the
safety boundary: `run(argv, cwd, timeout)` always takes an **argument list,
never a shell string**, and returns `(returncode, stdout, stderr)` instead of
raising. `have(exe)` checks PATH. Every command-wrapping skill goes through this.

**`CommandSkill`**
([skills/command_skill.py](../ai_agent_template/skills/command_skill.py)) is the
generic executor for **declarative** skills. Its class attributes (`command`,
`cwd_template`, `requires`, `timeout`, `max_output_lines`) are filled by the
loader from the markdown `execution` block. `run()`:

1. `_with_defaults()` — start from declared `default`s, overlay caller args.
2. `validate()` — required-param check.
3. `requires` preflight via `have()`.
4. `_subst()` — replace `{param}` in each argv token (as a single token → no
   injection).
5. `run()` the argv, truncate to `max_output_lines`, return `SkillResult`.

**`loader.py`** ([skills/loader.py](../ai_agent_template/skills/loader.py)) is
the discovery engine. `load_skills()` scans `skills_dir()` and handles **three
forms**:

- `skills/<name>.md` (single declarative file)
- `skills/<name>/SKILL.md` with an `execution` block (declarative folder)
- `skills/<name>/SKILL.md` + `skill.py` (coded)

`parse_skill_md()` splits frontmatter from body, validates `name`/`description`
and the hyphenated name format (`_NAME_RE`). `_build_skill_class()` picks the
class: a `skill.py` wins; otherwise `_build_command_class()` synthesizes a
`CommandSkill` subclass via `type(...)`. The loader then **stamps** the
frontmatter metadata onto the class and registers it — so docs and behavior
can't drift.

**`registry.py`** ([skills/registry.py](../ai_agent_template/skills/registry.py))
is a name→class map with **lazy loading**: the first call to
`get_skill`/`all_skills`/`registered_names` triggers `_ensure_loaded()` (which
runs the filesystem scan exactly once). `register`/`add` also lets you register
an in-code skill (handy in tests).

**Experiment (skills in isolation, no LLM):**
```bash
ai-agent list                       # shows discovered skills + descriptions

python -c "
from ai_agent_template.skills.registry import get_skill, registered_names
print(registered_names())
print(get_skill('code-search').run(pattern='def run', path='.').output[:300])"
```

### 4.4 The agent loop — `agents/base.py`

The heart of the system ([base.py](../ai_agent_template/agents/base.py)). Per
turn:

1. `provider.complete(system_prompt, messages)` — `_system_prompt()` renders the
   skill catalog (name, params, description) into `_SYSTEM_TEMPLATE`.
2. `_parse()` extracts the first JSON object, tolerating stray prose or code
   fences that small local models emit. On failure it nudges the model to retry
   valid JSON.
3. If `action == "final"` → return `AgentResult`.
4. Otherwise a **repeat-call guard**: a signature of `(action, args)` is cached;
   an identical repeat is *not* re-run — the prior observation is returned with a
   nudge to change course (this prevents a stuck model from burning the whole
   step budget retrying a failing call).
5. Dispatch the skill, append the observation, loop.
6. If `max_steps` (`AGENT_MAX_STEPS`, default 8) is hit, ask for a best-effort
   plain-text answer and return with `stopped_reason="max_steps"`.

`_dispatch()` turns every failure mode into a recoverable `[ERROR] …`
observation (unknown skill, missing param, or an unexpected skill exception) —
the loop never crashes on a bad model choice.

**Experiment (loop logic, NO LLM, using a scripted fake provider):**
```python
from ai_agent_template.agents.base import Agent
from ai_agent_template.agents.git_agent import GitAgent
from ai_agent_template.llm.base import LLMProvider

class FakeProvider(LLMProvider):
    name = "fake"
    def __init__(self, scripted): self.q = list(scripted)
    def stream(self, system, messages):
        yield self.q.pop(0)

provider = FakeProvider([
    '{"action":"code-search","args":{"pattern":"CommandSkill"}}',
    '{"action":"final","answer":"Found it in command_skill.py"}',
])
agent = GitAgent(provider)
result = agent.run("where is CommandSkill?")
print(result.stopped_reason, "->", result.answer)
for s in result.steps:
    print(s.action, s.args)
```

This is exactly how [tests/test_agent.py](../tests/test_agent.py) exercises the
loop deterministically.

### 4.5 GitAgent — `agents/git_agent.py`

A thin subclass ([git_agent.py](../ai_agent_template/agents/git_agent.py)): it
sets a `persona` and `CATEGORY = "git"`, and `_discover()` selects **every
registered skill tagged `category: git`**. That's why a newly added
`code-search.md` (which sets `metadata.category: git`) is usable with zero code
changes.

### 4.6 CLI — `cli.py`

Three subcommands ([cli.py](../ai_agent_template/cli.py)): `run` (build agent,
execute task, `-v` prints steps to stderr / answer to stdout), `list` (agents,
skills, providers), `health` (provider reachability). The entry point
`ai-agent` is declared in [pyproject.toml](../pyproject.toml).

## 5. Worked example: how `code-search` flows through the system

The file [skills/code-search.md](../skills/code-search.md) has **no Python**. At
startup:

- `loader.load_skills()` sees `skills/code-search.md`, confirms the stem matches
  `name: code-search`, and calls `parse_skill_md`.
- No `skill.py` exists for it, but the frontmatter has an `execution` block →
  `_build_command_class` creates a `CommandSkill_code_search` subclass with
  `command = ["git","-C","{path}","grep","-n","-I","--","{pattern}"]`,
  `requires=["git"]`, `max_output_lines=80`, and the `parameters` schema.
- Metadata (`category: git`, etc.) is stamped on; `registry.add` registers it.
- At runtime, `run(pattern="X", path=".")` → `_subst` produces
  `["git","-C",".","grep","-n","-I","--","X"]` → executed via `_run.run` →
  truncated `SkillResult`.

So the entire skill is **declarative config interpreted by `CommandSkill`** —
that is the "kind of code" it is.

## 6. How to test the complete system (by layer)

| Layer | Command | What it proves |
|------|---------|----------------|
| Unit/integration (offline) | `pytest -q` | skills, loader, parsing, agent loop (fake provider) |
| Discovery | `ai-agent list` | every `SKILL.md`/`.md` parses & registers |
| LLM connectivity | `ai-agent health` | Ollama/Anthropic reachable |
| One skill, no LLM | `python -c "...get_skill('code-search').run(...)"` | the skill works in isolation |
| Loop, no LLM | the `FakeProvider` snippet above | reasoning loop, guards, dispatch |
| Full end-to-end | `ai-agent run "<task>" -v` | CLI→agent→model→skill→answer |
| Cross-provider | `ai-agent run --provider anthropic "<task>"` | provider abstraction holds |
| CI | push / open PR | `pytest` on py 3.9/3.11/3.12 ([ci.yml](../.github/workflows/ci.yml)) |

End-to-end examples to try (local model):
```bash
ai-agent run "where is the repeat-call guard implemented?" -v   # → code-search
ai-agent run "show me the last 5 commits" -v                    # → git-log
ai-agent run "how active is this repo?" -v                      # → git-stats
ai-agent run "what changed in the last commit?" -v              # → github-diff
```

## 7. Extending the system

- **New declarative skill:** drop `skills/<name>.md` with `parameters` +
  `execution.command`; tag `category: git` to make `GitAgent` use it.
  *Constraint:* every `{placeholder}` must be `required` or have a `default`; the
  declarative path can't conditionally include flags.
- **New coded skill:** `skills/<name>/SKILL.md` + `skill.py` with a `Skill`
  subclass implementing `run()`.
- **New agent:** subclass `Agent`, set `persona` + skill selection, register in
  [agents/__init__.py](../ai_agent_template/agents/__init__.py) `AGENTS`.
- **New LLM backend:** subclass `LLMProvider.stream`, add a branch in
  `factory.get_provider`.

## 8. Design rationale (why it's built this way)

- **JSON protocol over native tool-calling** → one agent runs on any backend,
  including small local models.
- **Frontmatter as the single source of metadata** → docs (`SKILL.md`) and
  behavior never diverge.
- **`_run` argv-only** → LLM/user-supplied values can't inject shell commands.
- **Lazy filesystem discovery** → adding a skill needs no code edit and no import
  wiring.
- **Recoverable observations + repeat guard + step budget** → robust against the
  imperfect JSON and looping typical of smaller models.
