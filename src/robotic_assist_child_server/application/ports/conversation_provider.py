from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ConversationResponse:
    text: str
    expression: str = "happy"
    intent: str = "chat"
    image_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    system_prompt: str
    user_text: str
    session_id: str
    user_id: str
    messages: tuple[ConversationMessage, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class ConversationModelProvider(Protocol):
    """Port for conversation model providers (fake, OpenRouter, ...)."""

    async def generate(self, request: ConversationRequest) -> ConversationResponse:
        ...
