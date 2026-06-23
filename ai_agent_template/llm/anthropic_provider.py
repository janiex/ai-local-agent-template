"""External LLM backend via the Anthropic Claude API.

This is the "external LLM by API" option. Uses the official `anthropic` SDK
with streaming. The SDK is imported lazily so local-only users need not
install it.
"""
from __future__ import annotations

from typing import Iterator, List

from .base import LLMProvider, Message


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set — required for the external Claude backend."
            )
        import anthropic  # lazy import: only needed for this backend

        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key)

    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=8000,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def health_check(self) -> str:
        # A 1-token ping confirms the key and model are usable.
        self._client.messages.create(
            model=self.model,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return f"ok ({self.model})"
