from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    system_prompt: str
    user_text: str
    session_id: str
    user_id: str
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class ConversationModelProvider(Protocol):
    """Port for conversation model providers (fake, OpenRouter, ...)."""

    async def generate(self, request: ConversationRequest) -> str:
        ...
