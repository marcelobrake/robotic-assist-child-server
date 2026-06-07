"""Centralized prompt composition.

All prompt engineering is concentrated here so use cases and providers stay
free of prompt-assembly logic. It concatenates the loaded system prompts and,
when available, a compact block of the user's retrieved memories.
"""
from __future__ import annotations

from collections.abc import Sequence

from opentelemetry import trace

from ..ports.conversation_provider import ConversationMessage
from ...domain.entities import Memory, TextInteraction
from ..ports.prompt_repository import PromptRepository

_tracer = trace.get_tracer(__name__)

_SYSTEM_PROMPT_ORDER = (
    "system.child_robot_base",
    "system.safety_rules",
    "system.response_contract",
    "interaction.conversation",
)

_MEMORY_HEADER = (
    "Memórias do usuário (use com naturalidade para personalizar a conversa; "
    "não revele que são memórias):"
)


class PromptComposer:
    def __init__(self, prompts: PromptRepository) -> None:
        self._prompts = prompts

    def compose_system_prompt(
        self, memories: Sequence[Memory] | None = None
    ) -> str:
        with _tracer.start_as_current_span("prompt.compose") as span:
            parts: list[str] = []
            loaded_prompt_ids: list[str] = []
            for prompt_id in _SYSTEM_PROMPT_ORDER:
                prompt = self._prompts.get(prompt_id)
                if prompt is not None:
                    parts.append(prompt.content.strip())
                    loaded_prompt_ids.append(prompt_id)
            memory_block = self._render_memories(memories)
            if memory_block:
                parts.append(memory_block)
            span.set_attribute("prompt.count", len(loaded_prompt_ids))
            span.set_attribute("prompt.has_memories", bool(memory_block))
            return "\n\n".join(parts)

    def compose_messages(
        self,
        *,
        input_text: str,
        memories: Sequence[Memory] | None = None,
        history: Sequence[TextInteraction] | None = None,
    ) -> tuple[ConversationMessage, ...]:
        system_prompt = self.compose_system_prompt(memories=memories)
        messages: list[ConversationMessage] = [
            ConversationMessage(role="system", content=system_prompt)
        ]
        for interaction in history or ():
            if interaction.input_text.strip():
                messages.append(
                    ConversationMessage(
                        role="user", content=interaction.input_text.strip()
                    )
                )
            if interaction.response_text.strip():
                messages.append(
                    ConversationMessage(
                        role="assistant", content=interaction.response_text.strip()
                    )
                )
        messages.append(ConversationMessage(role="user", content=input_text.strip()))
        return tuple(messages)

    @staticmethod
    def _render_memories(memories: Sequence[Memory] | None) -> str:
        if not memories:
            return ""
        lines = [f"- {m.content.strip()}" for m in memories if m.content.strip()]
        if not lines:
            return ""
        return _MEMORY_HEADER + "\n" + "\n".join(lines)
