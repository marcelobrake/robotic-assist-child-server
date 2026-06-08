"""OpenAI adapters.

``OpenAISpeechToTextProvider`` implements the STT port using OpenAI's
``audio/transcriptions`` endpoint. Used only when ``STT_PROVIDER=openai``.
Input audio is never stored.
"""
from __future__ import annotations

from .openai_speech_to_text_provider import OpenAISpeechToTextProvider

__all__ = ["OpenAISpeechToTextProvider"]
