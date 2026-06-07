"""Fake conversation provider for the MVP slice.

Returns short, calm, child-safe responses in pt-BR without calling any external
API. The real OpenRouterConversationProvider will implement the same port.
"""
from __future__ import annotations

from ...application.ports.conversation_provider import ConversationRequest
from ...shared.logging import get_logger

logger = get_logger(__name__)

_GREETING_MARKERS = ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite")
_QUESTION_MARKER = "?"


class FakeConversationProvider:
    """Implements ConversationModelProvider with deterministic safe answers."""

    async def generate(self, request: ConversationRequest) -> str:
        text = request.user_text.strip().lower()
        logger.info(
            "fake conversation generate",
            extra={
                "event_name": "conversation.generate",
                "session_id": request.session_id,
                "user_id": request.user_id,
                "attributes": {"provider": "fake", "input_length": len(text)},
            },
        )

        if any(text.startswith(marker) for marker in _GREETING_MARKERS):
            return "Oi! Eu sou o Cubinho. Que bom falar com você! Vamos brincar?"
        if _QUESTION_MARKER in text:
            return (
                "Que pergunta legal! Eu ainda estou aprendendo. "
                "Você pode perguntar para o papai também."
            )
        return "Que legal! Me conta mais, eu adoro conversar com você."
