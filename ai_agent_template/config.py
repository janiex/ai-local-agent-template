"""Central configuration, loaded from environment / .env.

Deliberately import-light (only stdlib + python-dotenv) so it can be imported
from the CLI, tests, and any agent without pulling in optional dependencies
like the Anthropic SDK.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # LLM backend selection
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

    # Local LLM (Ollama)
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")

    # External LLM (Anthropic Claude API)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    # Agent loop
    agent_max_steps: int = _int("AGENT_MAX_STEPS", 8)

    # Skills: directory to discover SKILL.md skill folders in.
    # Empty = the project's top-level `skills/` directory.
    skills_dir: str = os.getenv("SKILLS_DIR", "")


settings = Settings()
