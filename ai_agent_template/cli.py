"""Command-line entry point for ai-agent-template.

Examples:
    ai-agent run "How active is this repo over the last month?"
    ai-agent run --agent git --provider anthropic "Summarize PR #7 in this repo"
    ai-agent list
    ai-agent health
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import skills as _skills  # provides all_skills() (lazy SKILL.md discovery)
from .agents import AGENTS
from .config import settings
from .llm.factory import available_providers, get_provider


def _build_agent(agent_name: str, provider_name: Optional[str], max_steps: Optional[int]):
    agent_cls = AGENTS.get(agent_name)
    if agent_cls is None:
        raise SystemExit(
            f"Unknown agent {agent_name!r}. Available: {', '.join(sorted(AGENTS))}"
        )
    provider = get_provider(provider_name)
    return agent_cls(provider, max_steps=max_steps)


def _cmd_run(args: argparse.Namespace) -> int:
    agent = _build_agent(args.agent, args.provider, args.max_steps)
    print(f"[{agent.name} via {agent.provider.name}] working...\n", file=sys.stderr)
    result = agent.run(args.task)

    if args.verbose:
        for i, step in enumerate(result.steps, 1):
            if step.action == "final":
                continue
            print(f"--- step {i}: {step.action}({step.args}) ---", file=sys.stderr)
            print(step.observation, file=sys.stderr)
            print(file=sys.stderr)

    print(result.answer)
    if result.stopped_reason != "final":
        print(f"\n[stopped: {result.stopped_reason}]", file=sys.stderr)
    return 0


def _cmd_list(_: argparse.Namespace) -> int:
    print("Agents:")
    for name, cls in sorted(AGENTS.items()):
        print(f"  {name:<10} {cls.__name__}")
    print("\nSkills:")
    for skill in _skills.all_skills():
        print(f"  {skill.name:<14} {skill.description}")
    print(f"\nLLM providers: {', '.join(available_providers())}")
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    provider = get_provider(args.provider)
    try:
        status = provider.health_check()
        print(f"{provider.name}: {status}")
        return 0
    except Exception as exc:  # network/auth errors are expected failure modes
        print(f"{provider.name}: FAILED — {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-agent", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an agent on a task.")
    run.add_argument("task", help="The natural-language task for the agent.")
    run.add_argument("--agent", default="git", help="Agent name (default: git).")
    run.add_argument(
        "--provider",
        default=None,
        choices=available_providers(),
        help=f"LLM backend (default from LLM_PROVIDER={settings.llm_provider}).",
    )
    run.add_argument("--max-steps", type=int, default=None, dest="max_steps")
    run.add_argument("-v", "--verbose", action="store_true", help="Show each step.")
    run.set_defaults(func=_cmd_run)

    lst = sub.add_parser("list", help="List available agents, skills, providers.")
    lst.set_defaults(func=_cmd_list)

    health = sub.add_parser("health", help="Check the LLM backend is reachable.")
    health.add_argument("--provider", default=None, choices=available_providers())
    health.set_defaults(func=_cmd_health)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
