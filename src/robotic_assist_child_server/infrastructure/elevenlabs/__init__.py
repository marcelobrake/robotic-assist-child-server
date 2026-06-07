"""Fake speech adapters prepared for future ElevenLabs integration.

Not wired into the MVP slice; defined so the STT/TTS ports have working
no-op implementations for future use cases and tests. No audio is stored.
"""
from __future__ import annotations


class FakeSpeechToTextProvider:
    async def transcribe(self, audio: bytes) -> str:
        return ""


class FakeTextToSpeechProvider:
    async def synthesize(self, text: str) -> bytes:
        return b""


__all__ = ["FakeSpeechToTextProvider", "FakeTextToSpeechProvider"]
