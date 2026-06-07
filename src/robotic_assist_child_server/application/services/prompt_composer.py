"""Centralized prompt composition.

All prompt engineering is concentrated here so use cases and providers stay
free of prompt-assembly logic. In the MVP slice it concatenates the loaded
system prompts into a single system prompt string.
"""
from __future__ import annotations

from ..ports.prompt_repository import PromptRepository

_SYSTEM_PROMPT_ORDER = (
    "system.child_robot_base",
    "system.safety_rules",
    "system.response_contract",
    "interaction.conversation",
)


class PromptComposer:
    def __init__(self, prompts: PromptRepository) -> None:
        self._prompts = prompts

    def compose_system_prompt(self) -> str:
        parts: list[str] = []
        for prompt_id in _SYSTEM_PROMPT_ORDER:
            prompt = self._prompts.get(prompt_id)
            if prompt is not None:
                parts.append(prompt.content.strip())
        return "\n\n".join(parts)
