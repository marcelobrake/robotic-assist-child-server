"""ElevenLabs adapters.

``FakeSpeechToTextProvider`` is a no-op kept for future STT work (no audio is
stored). ``FakeTextToSpeechProvider`` and ``ElevenLabsTextToSpeechProvider``
implement the TTS port and persist audio through the AudioStoragePort.
"""
from __future__ import annotations

from .elevenlabs_text_to_speech_provider import ElevenLabsTextToSpeechProvider
from .fake_text_to_speech_provider import FakeTextToSpeechProvider


class FakeSpeechToTextProvider:
    async def transcribe(self, audio: bytes) -> str:
        return ""


__all__ = [
    "ElevenLabsTextToSpeechProvider",
    "FakeSpeechToTextProvider",
    "FakeTextToSpeechProvider",
]
