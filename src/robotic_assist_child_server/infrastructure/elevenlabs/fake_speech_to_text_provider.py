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
            record_stt_duration(
                provider_name, (time.perf_counter() - started) * 1000
            )
            return SpeechTranscription(
                text=text,
                provider=provider_name,
                model=self._model,
                language=request.language,
            )
