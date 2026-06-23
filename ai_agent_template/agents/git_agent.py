"""The built-in GitAgent: inspects repositories using the git skills.

This is the reference agent the template ships with. It demonstrates the whole
pattern: pick skills, set a persona, inherit the loop. Copy this file to create
your own agent with a different skill set.
"""
from __future__ import annotations

from typing import List, Optional

from ..llm.base import LLMProvider
from ..skills.base import Skill
from ..skills.registry import all_skills
from .base import Agent


class GitAgent(Agent):
    name = "GitAgent"
    persona = (
        "an expert software-repository analyst. You answer questions about git "
        "repositories and GitHub pull requests by inspecting real data with your "
        "skills, then summarizing clearly for an engineer."
    )

    # Instead of a hard-coded list, this agent uses every registered skill
    # tagged with this category in its SKILL.md metadata. So adding a new
    # `skills/<name>.md` with `metadata.category: git` makes it available here
    # automatically — no code change required.
    CATEGORY = "git"

    def __init__(
        self,
        provider: LLMProvider,
        *,
        skills: Optional[List[Skill]] = None,
        max_steps: Optional[int] = None,
    ):
        resolved = skills if skills is not None else self._discover()
        super().__init__(provider, resolved, max_steps=max_steps)

    @classmethod
    def _discover(cls) -> List[Skill]:
        return [s for s in all_skills() if s.metadata.get("category") == cls.CATEGORY]
