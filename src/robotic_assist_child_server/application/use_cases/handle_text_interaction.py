"""Handle a single text interaction (MVP vertical slice).

Flow (subset of the full memory pipeline described in AGENT.md):
1. Validate input through the safety guard.
2. Compose the system prompt.
3. Generate a response via the conversation provider (fake in MVP), unless the
   request is unsafe — in that case return a gentle redirect.
4. Validate the response through the safety guard.
5. Build the interaction entity and persist it (best-effort).

Memory retrieval/update and async DB persistence are prepared via ports but
not wired to real adapters in this slice.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities import TextInteraction
from ...domain.enums import ClientType
from ...shared.datetime import utc_now
from ...shared.ids import new_interaction_id, new_session_id, new_user_id
from ..ports.conversation_provider import ConversationModelProvider, ConversationRequest
from ..ports.interaction_repository import InteractionRepository
from ..services.prompt_composer import PromptComposer
from ..services.safety_guard import SafetyGuard


@dataclass(frozen=True, slots=True)
class TextInteractionInput:
    text: str
    session_id: str | None = None
    user_id: str | None = None
    client_type: ClientType = ClientType.UNKNOWN
    device_id: str | None = None


class HandleTextInteraction:
    def __init__(
        self,
        *,
        composer: PromptComposer,
        provider: ConversationModelProvider,
        safety_guard: SafetyGuard,
        interaction_repository: InteractionRepository | None = None,
    ) -> None:
        self._composer = composer
        self._provider = provider
        self._safety = safety_guard
        self._interactions = interaction_repository

    async def execute(self, data: TextInteractionInput) -> TextInteraction:
        safe_input = self._safety.validate_input_text(data.text)
        session_id = data.session_id or new_session_id()
        user_id = data.user_id or new_user_id()

        if not self._safety.is_safe_request(safe_input):
            response_text = self._safety.redirect_message
        else:
            system_prompt = self._composer.compose_system_prompt()
            generated = await self._provider.generate(
                ConversationRequest(
                    system_prompt=system_prompt,
                    user_text=safe_input,
                    session_id=session_id,
                    user_id=user_id,
                )
            )
            response_text = self._safety.validate_assistant_response(generated)

        interaction = TextInteraction(
            interaction_id=new_interaction_id(),
            session_id=session_id,
            user_id=user_id,
            client_type=data.client_type,
            input_text=safe_input,
            response_text=response_text,
            created_at=utc_now(),
            device_id=data.device_id,
        )

        if self._interactions is not None:
            await self._interactions.save(interaction)

        return interaction
