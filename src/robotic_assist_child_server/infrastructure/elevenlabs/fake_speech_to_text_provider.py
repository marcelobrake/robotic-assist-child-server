"""Fake speech-to-text provider.

Keeps local development and tests independent from external APIs. It does not
call any service and does not store audio: it simply decodes the uploaded bytes
as UTF-8 text, which lets tests drive a deterministic transcription by sending
the desired transcript as the file body.
"""
from __future__ import annotations

import time

from opentelemetry import trace

from ...application.ports.speech import (
    SpeechTranscription,
    SpeechTranscriptionRequest,
)
from ...infrastructure.telemetry.metrics import (
    record_stt_duration,
    record_stt_request,
)

tracer = trace.get_tracer(__name__)

_BINARY_AUDIO_SIGNATURES = (
    b"\x00\x00\x00",  # m4a/mp4 boxes usually start with a null-padded size.
    b"\x1a\x45\xdf\xa3",  # webm/matroska.
    b"RIFF",  # wav.
    b"OggS",
    b"ID3",
)
_MIN_DECODED_TEXT_RATIO = 0.5
_MIN_PRINTABLE_TEXT_RATIO = 0.9


def _looks_like_binary_audio(audio: bytes, decoded_text: str) -> bool:
    if not audio:
        return False
    header = audio[:16]
    if any(header.startswith(signature) for signature in _BINARY_AUDIO_SIGNATURES):
        return True
    if b"\x00" in audio[:64]:
        return True
    if len(audio) < 32:
        return False
    if len(decoded_text.encode("utf-8", errors="ignore")) / len(audio) < _MIN_DECODED_TEXT_RATIO:
        return True
    printable = sum(1 for char in decoded_text if char.isprintable() or char.isspace())
    return bool(decoded_text) and printable / len(decoded_text) < _MIN_PRINTABLE_TEXT_RATIO


class FakeSpeechToTextProvider:
    def __init__(self, *, model: str = "fake-stt-placeholder") -> None:
        self._model = model

    async def transcribe(
        self, request: SpeechTranscriptionRequest
    ) -> SpeechTranscription:
        provider_name = "fake"
        record_stt_request(provider_name)
        started = time.perf_counter()
        with tracer.start_as_current_span("stt.provider.fake") as span:
            span.set_attribute("stt.provider", provider_name)
            span.set_attribute("stt.model", self._model)
            try:
                text = request.audio.decode("utf-8", errors="ignore").strip()
            except Exception:  # pragma: no cover - decode is defensive only
                text = ""
            if _looks_like_binary_audio(request.audio, text):
                raise RuntimeError(
                    "Fake STT cannot transcribe binary audio; enable a real STT provider."
                )
            record_stt_duration(
                provider_name, (time.perf_counter() - started) * 1000
            )
            return SpeechTranscription(
                text=text,
                provider=provider_name,
                model=self._model,
                language=request.language,
            )
