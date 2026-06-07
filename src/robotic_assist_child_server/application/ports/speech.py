"""Speech ports for ElevenLabs (STT/TTS).

STT remains a simple no-op contract (future work). TTS mirrors the image
generation port: a provider synthesizes audio and persists it through an
``AudioStoragePort`` so it can be served by ``GET /v1/audio/{audio_id}``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ...domain.entities import GeneratedAudio


@runtime_checkable
class SpeechToTextProvider(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


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
