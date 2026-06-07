"""Handle a single text interaction.

Flow (subset of the full pipeline in AGENT.md):
1. Validate input through the safety guard.
2. Retrieve user memories (identified users only) and compose the system prompt.
3. Generate a response via the conversation provider (fake in MVP), unless the
   request is unsafe — in that case return a gentle redirect.
4. Validate the response through the safety guard.
5. Build the interaction entity and persist it (best-effort).
6. Evaluate whether new memories should be created from the input.

Memory operations are best-effort: a memory backend hiccup must never break a
child's reply. Embeddings, vector search and LLM-based extraction are deferred.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from opentelemetry import trace

from ...domain.entities import TextInteraction
from ...domain.enums import ClientType
from ...shared.datetime import utc_now
from ...shared.ids import new_interaction_id, new_session_id, new_user_id
from ...shared.logging import get_logger
from ..ports.conversation_provider import (
    ConversationModelProvider,
    ConversationRequest,
    ConversationResponse,
)
from ..ports.interaction_repository import InteractionRepository
from ..ports.memory import MemoryRetriever, MemoryUpdater
from ..services.prompt_composer import PromptComposer
from ..services.safety_guard import SafetyGuard

_logger = get_logger(__name__)
_tracer = trace.get_tracer(__name__)


@dataclass(frozen=True, slots=True)
class TextInteractionInput:
    text: str
    session_id: str | None = None
    user_id: str | None = None
    client_type: ClientType = ClientType.UNKNOWN
    device_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class HandleTextInteraction:
    def __init__(
        self,
        *,
        composer: PromptComposer,
        provider: ConversationModelProvider,
        safety_guard: SafetyGuard,
        interaction_repository: InteractionRepository | None = None,
        memory_retriever: MemoryRetriever | None = None,
        memory_updater: MemoryUpdater | None = None,
    ) -> None:
        self._composer = composer
        self._provider = provider
        self._safety = safety_guard
        self._interactions = interaction_repository
        self._memory_retriever = memory_retriever
        self._memory_updater = memory_updater

    async def execute(self, data: TextInteractionInput) -> TextInteraction:
        safe_input = self._safety.validate_input_text(data.text)
        session_id = data.session_id or new_session_id()
        user_id = data.user_id or new_user_id()
        # Only persist/retrieve memory for identified users (auth or dev),
        # never for anonymous one-off ids.
        memory_user_id = data.user_id

        if not self._safety.is_safe_request(safe_input):
            generated = ConversationResponse(
                text=self._safety.redirect_message,
                expression="confused",
                intent="fallback",
                image_prompt=None,
            )
        else:
            memories = await self._retrieve_memories(memory_user_id, session_id)
            messages = self._composer.compose_messages(
                input_text=safe_input, memories=memories
            )
            system_prompt = messages[0].content if messages else ""
            with _tracer.start_as_current_span("conversation.generate") as span:
                span.set_attribute("client_type", data.client_type.value)
                generated = await self._provider.generate(
                    ConversationRequest(
                        system_prompt=system_prompt,
                        user_text=safe_input,
                        session_id=session_id,
                        user_id=user_id,
                        messages=messages,
                        metadata={
                            **data.metadata,
                            "client_type": data.client_type.value,
                        },
                    )
                )

        response_text = self._safety.validate_assistant_response(generated.text)

        interaction = TextInteraction(
            interaction_id=new_interaction_id(),
            session_id=session_id,
            user_id=user_id,
            client_type=data.client_type,
            input_text=safe_input,
            response_text=response_text,
            created_at=utc_now(),
            device_id=data.device_id,
            expression=generated.expression,
            intent=generated.intent,
            image_prompt=generated.image_prompt,
            status="accepted",
        )

        if self._interactions is not None:
            await self._interactions.save(interaction)

        await self._update_memories(memory_user_id, session_id, safe_input)
        return interaction

    async def _retrieve_memories(self, user_id, session_id):
        if not user_id or self._memory_retriever is None:
            return []
        try:
            return await self._memory_retriever.retrieve(user_id, session_id)
        except Exception:  # pragma: no cover - best-effort, never break the reply
            _logger.exception(
                "memory retrieval failed",
                extra={"event_name": "memory.retrieve", "user_id": user_id},
            )
            return []

    async def _update_memories(self, user_id, session_id, input_text) -> None:
        if not user_id or self._memory_updater is None:
            return
        try:
            await self._memory_updater.evaluate(
                user_id=user_id, session_id=session_id, input_text=input_text
            )
        except Exception:  # pragma: no cover - best-effort, never break the reply
            _logger.exception(
                "memory update failed",
                extra={"event_name": "memory.update", "user_id": user_id},
            )
