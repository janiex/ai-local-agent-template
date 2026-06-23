"""Local LLM backend via the Ollama REST API (no API key, runs offline)."""
from __future__ import annotations

import json
from typing import Iterator, List

import requests

from .base import LLMProvider, Message


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": True,
        }
        with requests.post(
            f"{self.host}/api/chat", json=payload, stream=True, timeout=600
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(f"Ollama error: {data['error']}")
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break

    def health_check(self) -> str:
        resp = requests.get(f"{self.host}/api/tags", timeout=10)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        if not any(self.model in m for m in models):
            return (
                f"Connected, but model '{self.model}' is not pulled. "
                f"Run: ollama pull {self.model}"
            )
        return f"ok ({self.model})"
