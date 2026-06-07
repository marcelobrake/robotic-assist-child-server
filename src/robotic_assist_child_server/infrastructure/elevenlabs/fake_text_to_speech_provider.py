"""Fake TTS provider for local development and tests.

Generates a short silent WAV file and stores it through the AudioStoragePort.
It performs no external calls and never receives or stores input audio.
"""
from __future__ import annotations

import struct
import time

from opentelemetry import trace

from ...application.ports.speech import AudioStoragePort, SpeechSynthesisRequest
from ...domain.entities import GeneratedAudio
from ...infrastructure.telemetry.metrics import (
    record_tts_duration,
    record_tts_request,
)
from ...shared.datetime import utc_now
from ...shared.ids import new_audio_id

tracer = trace.get_tracer(__name__)

_SAMPLE_RATE = 22050
_DURATION_MS = 200


class FakeTextToSpeechProvider:
    def __init__(
        self,
        *,
        audio_store: AudioStoragePort,
        model: str = "fake-tts-placeholder",
    ) -> None:
        self._audio_store = audio_store
        self._model = model

    async def synthesize(self, request: SpeechSynthesisRequest) -> GeneratedAudio:
        started = time.perf_counter()
        provider_name = "fake"
        record_tts_request(provider_name)

        with tracer.start_as_current_span("tts.provider.fake") as span:
            span.set_attribute("tts.provider", provider_name)
            span.set_attribute("tts.model", self._model)
            audio_id = new_audio_id()
            content = _silent_wav(_SAMPLE_RATE, _DURATION_MS)
            content_type = "audio/wav"
            path, audio_url = self._audio_store.save(
                audio_id=audio_id,
                content=content,
                content_type=content_type,
                output_format="wav",
            )
            record_tts_duration(provider_name, (time.perf_counter() - started) * 1000)
            return GeneratedAudio(
                audio_id=audio_id,
                audio_url=audio_url,
                content_type=content_type,
                provider=provider_name,
                model=self._model,
                created_at=utc_now(),
                duration_ms=_DURATION_MS,
                expires_at=None,
                storage_path=str(path),
            )


def _silent_wav(sample_rate: int, duration_ms: int) -> bytes:
    frames = max(1, int(sample_rate * duration_ms / 1000))
    data = b"\x00\x00" * frames  # 16-bit mono silence
    byte_rate = sample_rate * 2
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, byte_rate, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )
