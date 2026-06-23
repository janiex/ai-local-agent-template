"""ai-agent-template: an extensible framework for LLM agents that use skills.

Public surface kept small and stable so downstream code can build new agents
and skills without reaching into internals.
"""
from __future__ import annotations

from .agents.base import Agent, AgentResult, Step
from .skills.base import Skill, SkillResult
from .skills.registry import all_skills, get_skill, register

__all__ = [
    "Agent",
    "AgentResult",
    "Step",
    "Skill",
    "SkillResult",
    "register",
    "get_skill",
    "all_skills",
]

__version__ = "0.1.0"
