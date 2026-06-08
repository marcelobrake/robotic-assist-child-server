"""Speech ports for ElevenLabs/OpenAI (STT/TTS).

STT transcribes uploaded audio bytes into text through a pluggable provider
(ElevenLabs by default, OpenAI optional). TTS mirrors the image generation
port: a provider synthesizes audio and persists it through an
``AudioStoragePort`` so it can be served by ``GET /v1/audio/{audio_id}``.

Input audio is never stored: providers receive the bytes in-memory and the
endpoint discards them after transcription.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ...domain.entities import GeneratedAudio


@dataclass(frozen=True, slots=True)
class SpeechTranscriptionRequest:
    audio: bytes
    content_type: str
    session_id: str
    user_id: str
    filename: str = "audio"
    language: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SpeechTranscription:
    text: str
    provider: str
    model: str
    language: str | None = None


class SpeechProviderError(RuntimeError):
    """Base exception for speech provider failures."""


class SpeechProviderConfigurationError(SpeechProviderError):
    """Raised when STT/TTS provider credentials or configuration are invalid."""


@runtime_checkable
class SpeechToTextProvider(Protocol):
    async def transcribe(
        self, request: SpeechTranscriptionRequest
    ) -> SpeechTranscription: ...


@dataclass(frozen=True, slots=True)
class SpeechSynthesisRequest:
    text: str
    session_id: str
    user_id: str
    output_format: str = "mp3_44100_128"
    voice_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class TextToSpeechProvider(Protocol):
    async def synthesize(self, request: SpeechSynthesisRequest) -> GeneratedAudio: ...


@dataclass(frozen=True, slots=True)
class StoredAudio:
    path: Path
    content_type: str


@runtime_checkable
class AudioStoragePort(Protocol):
    def save(
        self, *, audio_id: str, content: bytes, content_type: str, output_format: str
    ) -> tuple[Path, str]: ...

    def resolve(self, audio_id: str) -> StoredAudio | None: ...
