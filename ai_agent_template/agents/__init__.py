"""Agents. The base loop lives in `base`; concrete agents bundle skills.

Register new agents in `AGENTS` so the CLI can discover them by name.
"""
from __future__ import annotations

from typing import Dict, Type

from .base import Agent, AgentResult, Step
from .git_agent import GitAgent

# name -> Agent subclass, for CLI discovery and easy extension.
AGENTS: Dict[str, Type[Agent]] = {
    "git": GitAgent,
}

__all__ = ["Agent", "AgentResult", "Step", "GitAgent", "AGENTS"]
