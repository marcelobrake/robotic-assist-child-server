"""Speech ports prepared for ElevenLabs (STT/TTS). Not used in the MVP slice."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SpeechToTextProvider(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


@runtime_checkable
class TextToSpeechProvider(Protocol):
    async def synthesize(self, text: str) -> bytes: ...
