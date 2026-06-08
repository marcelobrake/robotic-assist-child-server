"""ElevenLabs adapters.

``FakeSpeechToTextProvider`` keeps STT independent from external APIs (no audio
is stored; it decodes the uploaded bytes as text). ``FakeTextToSpeechProvider``
and ``ElevenLabsTextToSpeechProvider`` implement the TTS port and persist audio
through the AudioStoragePort. ``ElevenLabsSpeechToTextProvider`` implements the
STT port. Input audio is never stored.
"""
from __future__ import annotations

from .elevenlabs_speech_to_text_provider import ElevenLabsSpeechToTextProvider
from .elevenlabs_text_to_speech_provider import ElevenLabsTextToSpeechProvider
from .fake_speech_to_text_provider import FakeSpeechToTextProvider
from .fake_text_to_speech_provider import FakeTextToSpeechProvider

__all__ = [
    "ElevenLabsSpeechToTextProvider",
    "ElevenLabsTextToSpeechProvider",
    "FakeSpeechToTextProvider",
    "FakeTextToSpeechProvider",
]
