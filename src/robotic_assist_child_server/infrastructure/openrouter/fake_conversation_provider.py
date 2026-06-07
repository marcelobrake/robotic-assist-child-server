"""Fake conversation provider for the MVP slice.

Returns short, calm, child-safe responses in pt-BR without calling any external
API. The real OpenRouterConversationProvider will implement the same port.
"""
from __future__ import annotations

import time

from opentelemetry import trace

from ...application.ports.conversation_provider import (
    ConversationRequest,
    ConversationResponse,
)
from ...infrastructure.telemetry.metrics import (
    record_conversation_duration,
    record_conversation_request,
)
from ...shared.logging import get_logger

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

_GREETING_MARKERS = ("oi", "olá", "ola", "bom dia", "boa tarde", "boa noite")
_IMAGE_MARKERS = ("desenha", "desenhe", "desenhar", "imagem", "foto", "pinte")
_QUESTION_MARKER = "?"


class FakeConversationProvider:
    """Implements ConversationModelProvider with deterministic safe answers."""

    async def generate(self, request: ConversationRequest) -> ConversationResponse:
        started = time.perf_counter()
        text = request.user_text.strip().lower()
        record_conversation_request("fake")

        with tracer.start_as_current_span("conversation.provider.fake") as span:
            span.set_attribute("conversation.provider", "fake")
            span.set_attribute("conversation.input_length", len(text))
            logger.info(
                "fake conversation generate",
                extra={
                    "event_name": "conversation.provider.fake",
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "attributes": {"provider": "fake", "input_length": len(text)},
                },
            )

            if any(marker in text for marker in _IMAGE_MARKERS):
                response = ConversationResponse(
                    text="Posso imaginar isso com você! Vou preparar um desenho seguro.",
                    expression="happy",
                    intent="generate_image",
                    image_prompt=request.user_text.strip(),
                )
            elif any(text.startswith(marker) for marker in _GREETING_MARKERS):
                response = ConversationResponse(
                    text="Oi! Eu sou o Cubinho. Que bom falar com você! Vamos brincar?",
                    expression="happy",
                    intent="chat",
                )
            elif _QUESTION_MARKER in text:
                response = ConversationResponse(
                    text=(
                        "Que pergunta legal! Eu ainda estou aprendendo. "
                        "Você pode perguntar para o papai também."
                    ),
                    expression="thinking",
                    intent="chat",
                )
            else:
                response = ConversationResponse(
                    text="Que legal! Me conta mais, eu adoro conversar com você.",
                    expression="happy",
                    intent="chat",
                )
            record_conversation_duration(
                "fake", (time.perf_counter() - started) * 1000
            )
            return response
