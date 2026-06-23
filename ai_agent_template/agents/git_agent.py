"""The built-in GitAgent: inspects repositories using the git skills.

This is the reference agent the template ships with. It demonstrates the whole
pattern: pick skills, set a persona, inherit the loop. Copy this file to create
your own agent with a different skill set.
"""
from __future__ import annotations

from typing import List, Optional

from ..llm.base import LLMProvider
from ..skills.base import Skill
from ..skills.registry import get_skill
from .base import Agent


class GitAgent(Agent):
    name = "GitAgent"
    persona = (
        "an expert software-repository analyst. You answer questions about git "
        "repositories and GitHub pull requests by inspecting real data with your "
        "skills, then summarizing clearly for an engineer."
    )

    # The skills this agent is allowed to use, by registered name.
    SKILL_NAMES = ["git_stats", "github_diff"]

    def __init__(
        self,
        provider: LLMProvider,
        *,
        skills: Optional[List[Skill]] = None,
        max_steps: Optional[int] = None,
    ):
        resolved = skills or [get_skill(n) for n in self.SKILL_NAMES]
        super().__init__(provider, resolved, max_steps=max_steps)
