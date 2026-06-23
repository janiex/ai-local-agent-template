"""Agent-loop tests using a scripted fake provider (no network, no LLM)."""
from __future__ import annotations

from typing import Iterator, List

from ai_agent_template.agents.base import Agent
from ai_agent_template.llm.base import LLMProvider, Message
from ai_agent_template.skills.base import Skill, SkillResult


class FakeProvider(LLMProvider):
    """Replays a queue of canned responses, one per `complete` call."""

    name = "fake"

    def __init__(self, scripted: List[str]):
        self._queue = list(scripted)

    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        yield self._queue.pop(0) if self._queue else '{"action":"final","answer":"done"}'


class EchoSkill(Skill):
    name = "echo"
    description = "Echo back the text argument."
    parameters = {"text": {"type": "string", "required": True}}

    def run(self, **kwargs):
        self.validate(kwargs)
        return SkillResult(True, f"echo: {kwargs['text']}")


def test_agent_calls_skill_then_finalizes():
    provider = FakeProvider(
        [
            '{"thought":"use echo","action":"echo","args":{"text":"hi"}}',
            '{"thought":"got it","action":"final","answer":"The echo said hi."}',
        ]
    )
    agent = Agent(provider, [EchoSkill()])
    result = agent.run("say hi")

    assert result.stopped_reason == "final"
    assert result.answer == "The echo said hi."
    assert result.steps[0].action == "echo"
    assert "echo: hi" in result.steps[0].observation


def test_agent_recovers_from_bad_json():
    provider = FakeProvider(
        [
            "I think I should echo something.",  # invalid: not JSON
            '{"action":"final","answer":"ok"}',
        ]
    )
    agent = Agent(provider, [EchoSkill()])
    result = agent.run("anything")
    assert result.answer == "ok"


def test_agent_reports_unknown_skill():
    provider = FakeProvider(
        [
            '{"action":"nope","args":{}}',
            '{"action":"final","answer":"handled"}',
        ]
    )
    agent = Agent(provider, [EchoSkill()])
    result = agent.run("x")
    assert "Unknown skill" in result.steps[0].observation
    assert result.answer == "handled"


def test_agent_does_not_rerun_identical_calls():
    # Two identical echo calls, then finalize. The skill must run only once.
    calls = []

    class CountingSkill(EchoSkill):
        name = "echo"

        def run(self, **kwargs):
            calls.append(kwargs)
            return super().run(**kwargs)

    provider = FakeProvider(
        [
            '{"action":"echo","args":{"text":"hi"}}',
            '{"action":"echo","args":{"text":"hi"}}',
            '{"action":"final","answer":"done"}',
        ]
    )
    agent = Agent(provider, [CountingSkill()])
    result = agent.run("repeat")
    assert result.answer == "done"
    assert len(calls) == 1  # second identical call was served from cache
    assert "already made this exact call" in result.steps[1].observation


def test_agent_stops_at_max_steps():
    # Always asks to call a skill, never finalizes.
    provider = FakeProvider(['{"action":"echo","args":{"text":"loop"}}'] * 20)
    agent = Agent(provider, [EchoSkill()], max_steps=3)
    result = agent.run("loop forever")
    assert result.stopped_reason == "max_steps"
