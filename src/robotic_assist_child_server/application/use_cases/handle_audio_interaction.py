"""Handle a single audio (voice) interaction.

Flow:
1. Transcribe the uploaded audio via a pluggable SpeechToTextProvider.
2. In listener mode, classify whether the utterance is addressed to the robot;
   if not, return an ``ignored`` interaction (optionally persisted) without
   calling the conversation model.
3. Otherwise, feed the transcribed text into the exact same pipeline as
   ``/v1/interactions/text`` (memory, prompt composition, safety, conversation,
   optional TTS), reusing ``HandleTextInteraction``.

Input audio is never stored: the bytes live only for the duration of the call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from opentelemetry import trace

from ...domain.entities import TextInteraction
from ...domain.enums import ClientType
from ...infrastructure.telemetry.metrics import record_audio_ignored
from ...shared.datetime import utc_now
from ...shared.errors import SpeechTranscriptionError
from ...shared.ids import new_interaction_id, new_session_id, new_user_id
from ...shared.logging import get_logger
from ..ports.interaction_repository import InteractionRepository
from ..ports.speech import (
    SpeechToTextProvider,
    SpeechTranscriptionRequest,
)
from ..ports.speech_intent import SpeechIntentClassifier
from .handle_text_interaction import HandleTextInteraction, TextInteractionInput

_logger = get_logger(__name__)
_tracer = trace.get_tracer(__name__)


@dataclass(frozen=True, slots=True)
class AudioInteractionInput:
    audio: bytes
    content_type: str
    session_id: str | None = None
    user_id: str | None = None
    client_type: ClientType = ClientType.UNKNOWN
    device_id: str | None = None
    generate_audio: bool = False
    listener_mode: bool = False
    language: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class HandleAudioInteraction:
    def __init__(
        self,
        *,
        stt_provider: SpeechToTextProvider,
        text_handler: HandleTextInteraction,
        intent_classifier: SpeechIntentClassifier,
        interaction_repository: InteractionRepository | None = None,
        store_ignored_interactions: bool = False,
    ) -> None:
        self._stt = stt_provider
        self._text_handler = text_handler
        self._intent_classifier = intent_classifier
        self._interactions = interaction_repository
        self._store_ignored = store_ignored_interactions

    async def execute(self, data: AudioInteractionInput) -> TextInteraction:
        session_id = data.session_id or new_session_id()
        user_id = data.user_id or new_user_id()

        with _tracer.start_as_current_span("interaction.handle_audio") as span:
            span.set_attribute("client_type", data.client_type.value)
            span.set_attribute("audio.listener_mode", data.listener_mode)

            transcribed = await self._transcribe(data, session_id, user_id)
            text = transcribed.strip()
            span.set_attribute("stt.empty", not text)

            if data.listener_mode:
                ignored = self._evaluate_listener_mode(
                    text=text,
                    data=data,
                    session_id=session_id,
                    user_id=user_id,
                )
                if ignored is not None:
                    await self._maybe_persist_ignored(ignored)
                    return ignored

            return await self._text_handler.execute(
                TextInteractionInput(
                    text=text,
                    session_id=session_id,
                    user_id=user_id,
                    client_type=data.client_type,
                    device_id=data.device_id,
                    generate_audio=data.generate_audio,
                    metadata=data.metadata,
                )
            )

    async def _transcribe(
        self, data: AudioInteractionInput, session_id: str, user_id: str
    ) -> str:
        with _tracer.start_as_current_span("stt.transcribe") as span:
            span.set_attribute("client_type", data.client_type.value)
            try:
                result = await self._stt.transcribe(
                    SpeechTranscriptionRequest(
                        audio=data.audio,
                        content_type=data.content_type,
                        session_id=session_id,
                        user_id=user_id,
                        language=data.language,
                        metadata={
                            **data.metadata,
                            "client_type": data.client_type.value,
                        },
                    )
                )
            except Exception as exc:
                _logger.warning(
                    "speech transcription failed",
                    extra={
                        "event_name": "stt.transcribe",
                        "session_id": session_id,
                        "user_id": user_id,
                        "attributes": {
                            "client_type": data.client_type.value,
                            "error_type": exc.__class__.__name__,
                        },
                    },
                )
                raise SpeechTranscriptionError(
                    "Não consegui entender o áudio agora. Tente novamente."
                ) from exc
            span.set_attribute("stt.provider", result.provider)
            return result.text

    def _evaluate_listener_mode(
        self,
        *,
        text: str,
        data: AudioInteractionInput,
        session_id: str,
        user_id: str,
    ) -> TextInteraction | None:
        with _tracer.start_as_current_span("speech_intent.classify") as span:
            decision = self._intent_classifier.classify(text)
            span.set_attribute("speech_intent.should_respond", decision.should_respond)
            span.set_attribute("speech_intent.reason", decision.reason)
        if decision.should_respond:
            return None

        with _tracer.start_as_current_span("interaction.audio.ignored") as span:
            span.set_attribute("speech_intent.reason", decision.reason)
            record_audio_ignored(decision.reason)
            _logger.info(
                "audio interaction ignored in listener mode",
                extra={
                    "event_name": "interaction.audio.ignored",
                    "session_id": session_id,
                    "user_id": user_id,
                    "attributes": {"reason": decision.reason},
                },
            )
        return TextInteraction(
            interaction_id=new_interaction_id(),
            session_id=session_id,
            user_id=user_id,
            client_type=data.client_type,
            input_text=text,
            response_text="",
            created_at=utc_now(),
            device_id=data.device_id,
            expression="idle",
            intent="ignored",
            image_prompt=None,
            image=None,
            audio=None,
            status="ignored",
            ignored_reason=decision.reason,
        )

    async def _maybe_persist_ignored(self, interaction: TextInteraction) -> None:
        if not self._store_ignored or self._interactions is None:
            return
        try:
            await self._interactions.save(interaction)
        except Exception:  # pragma: no cover - best-effort persistence
            _logger.exception(
                "failed to persist ignored interaction",
                extra={
                    "event_name": "repository.interaction.save",
                    "session_id": interaction.session_id,
                },
            )
