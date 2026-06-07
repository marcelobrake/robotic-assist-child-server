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
from ..ports.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from ..ports.interaction_repository import InteractionRepository
from ..ports.memory import MemoryRetriever, MemoryUpdater
from ..ports.speech import SpeechSynthesisRequest, TextToSpeechProvider
from ..services.prompt_composer import PromptComposer
from ..services.safety_guard import SafetyGuard

_logger = get_logger(__name__)
_tracer = trace.get_tracer(__name__)
_SESSION_HISTORY_LIMIT = 8
_RETRY_MARKERS = (
    "tente novamente",
    "tenta novamente",
    "tentar novamente",
    "tente de novo",
    "tenta de novo",
    "de novo",
    "novamente",
)


@dataclass(frozen=True, slots=True)
class TextInteractionInput:
    text: str
    session_id: str | None = None
    user_id: str | None = None
    client_type: ClientType = ClientType.UNKNOWN
    device_id: str | None = None
    generate_audio: bool = False
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
        image_provider: ImageGenerationProvider | None = None,
        image_generation_enabled: bool = False,
        image_default_aspect_ratio: str = "1:1",
        image_default_size: str = "800x800",
        image_output_format: str = "png",
        tts_provider: TextToSpeechProvider | None = None,
        tts_enabled: bool = False,
        tts_default_output_format: str = "mp3_44100_128",
        tts_voice_id: str | None = None,
    ) -> None:
        self._composer = composer
        self._provider = provider
        self._safety = safety_guard
        self._interactions = interaction_repository
        self._memory_retriever = memory_retriever
        self._memory_updater = memory_updater
        self._image_provider = image_provider
        self._image_generation_enabled = image_generation_enabled
        self._image_default_aspect_ratio = image_default_aspect_ratio
        self._image_default_size = image_default_size
        self._image_output_format = image_output_format
        self._tts_provider = tts_provider
        self._tts_enabled = tts_enabled
        self._tts_default_output_format = tts_default_output_format
        self._tts_voice_id = tts_voice_id

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
            history = await self._retrieve_session_history(session_id)
            retry_target = self._select_retry_target(safe_input, history)
            model_input = retry_target.input_text if retry_target else safe_input
            messages = self._composer.compose_messages(
                input_text=model_input, memories=memories, history=history
            )
            system_prompt = messages[0].content if messages else ""
            with _tracer.start_as_current_span("conversation.generate") as span:
                span.set_attribute("client_type", data.client_type.value)
                span.set_attribute("conversation.has_history", bool(history))
                span.set_attribute("conversation.retry", retry_target is not None)
                if retry_target is not None:
                    span.set_attribute(
                        "conversation.retry_interaction_id",
                        retry_target.interaction_id,
                    )
                generated = await self._provider.generate(
                    ConversationRequest(
                        system_prompt=system_prompt,
                        user_text=model_input,
                        session_id=session_id,
                        user_id=user_id,
                        messages=messages,
                        metadata={
                            **data.metadata,
                            "client_type": data.client_type.value,
                            **(
                                {"retry_of_interaction_id": retry_target.interaction_id}
                                if retry_target is not None
                                else {}
                            ),
                        },
                    )
                )

        response_text = self._safety.validate_assistant_response(generated.text)
        image = await self._maybe_generate_image(
            generated=generated,
            data=data,
            session_id=session_id,
            user_id=user_id,
        )
        audio = await self._maybe_generate_audio(
            response_text=response_text,
            data=data,
            session_id=session_id,
            user_id=user_id,
        )

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
            image=image,
            audio=audio,
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

    async def _retrieve_session_history(self, session_id: str):
        if self._interactions is None:
            return []
        try:
            return await self._interactions.list_recent_by_session(
                session_id, limit=_SESSION_HISTORY_LIMIT
            )
        except Exception:  # pragma: no cover - best-effort, never break the reply
            _logger.exception(
                "session history retrieval failed",
                extra={"event_name": "conversation.history", "session_id": session_id},
            )
            return []

    def _select_retry_target(self, input_text: str, history):
        if not self._is_retry_request(input_text) or not history:
            return None
        for interaction in reversed(history):
            if (
                interaction.intent == "generate_image"
                and interaction.image_prompt
                and interaction.image is None
            ):
                return interaction
        for interaction in reversed(history):
            if not self._is_retry_request(interaction.input_text):
                return interaction
        return None

    @staticmethod
    def _is_retry_request(input_text: str) -> bool:
        lowered = input_text.strip().lower()
        return any(marker in lowered for marker in _RETRY_MARKERS)

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

    async def _maybe_generate_image(
        self,
        *,
        generated: ConversationResponse,
        data: TextInteractionInput,
        session_id: str,
        user_id: str,
    ):
        if (
            generated.intent != "generate_image"
            or not generated.image_prompt
            or not self._image_generation_enabled
            or self._image_provider is None
        ):
            return None

        with _tracer.start_as_current_span("image.generate") as span:
            span.set_attribute("client_type", data.client_type.value)
            span.set_attribute("image.enabled", True)
            try:
                with _tracer.start_as_current_span("image.prompt.validate"):
                    image_prompt = self._safety.validate_input_text(
                        generated.image_prompt
                    )
                    if not self._safety.is_safe_request(image_prompt):
                        _logger.warning(
                            "unsafe image prompt rejected",
                            extra={
                                "event_name": "image.prompt.validate",
                                "session_id": session_id,
                                "user_id": user_id,
                                "attributes": {"reason": "unsafe_prompt"},
                            },
                        )
                        return None

                return await self._image_provider.generate(
                    ImageGenerationRequest(
                        prompt=image_prompt,
                        session_id=session_id,
                        user_id=user_id,
                        aspect_ratio=data.metadata.get(
                            "aspect_ratio", self._image_default_aspect_ratio
                        ),
                        size=data.metadata.get("size", self._image_default_size),
                        output_format=data.metadata.get(
                            "output_format", self._image_output_format
                        ),
                        metadata={
                            **data.metadata,
                            "client_type": data.client_type.value,
                        },
                    )
                )
            except Exception:  # pragma: no cover - provider fallback is primary path
                _logger.exception(
                    "image generation failed",
                    extra={
                        "event_name": "image.generate",
                        "session_id": session_id,
                        "user_id": user_id,
                    },
                )
                return None

    async def _maybe_generate_audio(
        self,
        *,
        response_text: str,
        data: TextInteractionInput,
        session_id: str,
        user_id: str,
    ):
        if (
            not data.generate_audio
            or not self._tts_enabled
            or self._tts_provider is None
            or not response_text.strip()
        ):
            return None

        # Best-effort: a TTS error must never break the child's textual reply.
        with _tracer.start_as_current_span("tts.generate") as span:
            span.set_attribute("client_type", data.client_type.value)
            span.set_attribute("tts.enabled", True)
            try:
                return await self._tts_provider.synthesize(
                    SpeechSynthesisRequest(
                        text=response_text,
                        session_id=session_id,
                        user_id=user_id,
                        output_format=data.metadata.get(
                            "tts_output_format", self._tts_default_output_format
                        ),
                        voice_id=data.metadata.get("voice_id", self._tts_voice_id),
                        metadata={
                            **data.metadata,
                            "client_type": data.client_type.value,
                        },
                    )
                )
            except Exception:  # pragma: no cover - audio is best-effort
                _logger.exception(
                    "tts generation failed",
                    extra={
                        "event_name": "tts.generate",
                        "session_id": session_id,
                        "user_id": user_id,
                    },
                )
                return None
