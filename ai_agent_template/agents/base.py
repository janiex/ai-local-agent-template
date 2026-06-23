"""The Agent base class: a provider-agnostic reason -> act -> observe loop.

Why a JSON protocol instead of provider-native tool calling? It works
identically across a local Ollama model and the Claude API, so the same agent
runs on either backend. Each step the LLM returns one JSON object:

    {"thought": "...", "action": "skill_name", "args": {...}}
  or
    {"thought": "...", "action": "final", "answer": "..."}

The loop executes the chosen skill, appends the observation, and repeats until
the model answers or `max_steps` is reached.

Subclass this (see `agents/git_agent.py`) to bundle a fixed set of skills and a
specialized persona. Most subclasses only need to set defaults — the loop is
inherited.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import settings
from ..llm.base import LLMProvider
from ..skills.base import Skill

_SYSTEM_TEMPLATE = """You are {name}, {persona}

You solve the user's task by calling skills (tools) one at a time. On EACH turn
you must reply with EXACTLY ONE JSON object and nothing else — no prose, no code
fences. Use one of these two shapes:

  {{"thought": "<brief reasoning>", "action": "<skill_name>", "args": {{...}}}}
  {{"thought": "<brief reasoning>", "action": "final", "answer": "<your answer>"}}

Call "final" when you have enough information to answer the user directly.

Available skills:
{catalog}

Rules:
- "action" must be one of: {skill_names}, or "final".
- "args" keys must match the skill's parameters.
- Never invent skill output; rely only on the observations provided.
"""


@dataclass
class Step:
    """One iteration of the loop, kept for transparency / debugging."""

    thought: str
    action: str
    args: Dict[str, Any] = field(default_factory=dict)
    observation: str = ""


@dataclass
class AgentResult:
    answer: str
    steps: List[Step] = field(default_factory=list)
    stopped_reason: str = "final"  # "final" | "max_steps" | "error"


class Agent:
    # Subclasses override these.
    name: str = "Agent"
    persona: str = "a helpful assistant."

    def __init__(
        self,
        provider: LLMProvider,
        skills: Optional[List[Skill]] = None,
        *,
        max_steps: Optional[int] = None,
    ):
        self.provider = provider
        self.skills: Dict[str, Skill] = {s.name: s for s in (skills or [])}
        self.max_steps = max_steps or settings.agent_max_steps

    # ---- public API ------------------------------------------------------
    def run(self, task: str) -> AgentResult:
        messages = [{"role": "user", "content": f"Task: {task}"}]
        steps: List[Step] = []
        seen: Dict[str, str] = {}  # signature -> observation, to break repeat loops

        for _ in range(self.max_steps):
            raw = self.provider.complete(self._system_prompt(), messages)
            try:
                decision = self._parse(raw)
            except ValueError as exc:
                # Nudge the model back to valid JSON and try again.
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {"role": "user", "content": f"Invalid response ({exc}). "
                     "Reply with a single valid JSON object as instructed."}
                )
                continue

            action = decision.get("action", "")
            thought = str(decision.get("thought", ""))

            if action == "final":
                answer = str(decision.get("answer", "")).strip()
                steps.append(Step(thought, "final", {}, answer))
                return AgentResult(answer, steps, "final")

            args = decision.get("args", {}) or {}
            signature = f"{action}|{json.dumps(args, sort_keys=True, default=str)}"
            if signature in seen:
                # The model is repeating an identical call — don't re-run it;
                # hand back the prior result and steer it somewhere new.
                observation = (
                    seen[signature]
                    + "\n(You already made this exact call and got the result above. "
                    "Try different arguments, a different skill, or reply with "
                    'action "final".)'
                )
            else:
                observation = self._dispatch(action, args)
                seen[signature] = observation
            step = Step(thought, action, args, observation)
            steps.append(step)

            # Feed the action + observation back so the model can continue.
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        # Exhausted the step budget — ask for a best-effort answer.
        final = self.provider.complete(
            self._system_prompt(),
            messages + [{"role": "user", "content":
                         "Step budget reached. Give your best final answer as plain text."}],
        )
        return AgentResult(final.strip(), steps, "max_steps")

    # ---- internals -------------------------------------------------------
    def _dispatch(self, action: str, args: Dict[str, Any]) -> str:
        skill = self.skills.get(action)
        if skill is None:
            return f"[ERROR] Unknown skill '{action}'. Choose one of: {list(self.skills)}."
        try:
            result = skill.run(**args)
        except ValueError as exc:  # e.g. missing required parameter
            return f"[ERROR] {exc}"
        except Exception as exc:  # defensive: skill bug shouldn't kill the loop
            return f"[ERROR] Skill '{action}' raised: {exc}"
        return result.as_observation()

    def _system_prompt(self) -> str:
        catalog = "\n".join(self._describe(s) for s in self.skills.values())
        return _SYSTEM_TEMPLATE.format(
            name=self.name,
            persona=self.persona,
            catalog=catalog or "  (none)",
            skill_names=", ".join(self.skills) or "(none)",
        )

    @staticmethod
    def _describe(skill: Skill) -> str:
        params = ", ".join(
            f"{p}{'*' if spec.get('required') else ''}:{spec.get('type', 'string')}"
            for p, spec in skill.parameters.items()
        )
        return f"- {skill.name}({params}): {skill.description}"

    @staticmethod
    def _parse(raw: str) -> Dict[str, Any]:
        """Extract the first JSON object from the model's reply, tolerating
        stray prose or markdown fences that smaller local models sometimes add."""
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):] if "{" in text else text
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("no JSON object found")
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSON: {exc}") from None
        if not isinstance(obj, dict) or "action" not in obj:
            raise ValueError("missing 'action' field")
        return obj
