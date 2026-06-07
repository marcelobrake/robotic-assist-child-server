"""Best-effort OpenTelemetry metrics helpers."""
from __future__ import annotations

from typing import Any

try:  # pragma: no cover - depends on optional OTel runtime wiring
    from opentelemetry import metrics

    _meter = metrics.get_meter("robotic_assist_child_server.conversation")
    _request_count = _meter.create_counter("conversation.request.count")
    _error_count = _meter.create_counter("conversation.error.count")
    _duration_ms = _meter.create_histogram("conversation.duration_ms")
    _fallback_count = _meter.create_counter("conversation.fallback.count")
    _image_request_count = _meter.create_counter("image.request.count")
    _image_error_count = _meter.create_counter("image.error.count")
    _image_duration_ms = _meter.create_histogram("image.duration_ms")
    _image_fallback_count = _meter.create_counter("image.fallback.count")
    _image_serve_count = _meter.create_counter("image.serve.count")
    _tts_request_count = _meter.create_counter("tts.request.count")
    _tts_error_count = _meter.create_counter("tts.error.count")
    _tts_duration_ms = _meter.create_histogram("tts.duration_ms")
    _audio_serve_count = _meter.create_counter("audio.serve.count")
except Exception:  # pragma: no cover - no-op if OTel is unavailable
    _request_count = None
    _error_count = None
    _duration_ms = None
    _fallback_count = None
    _image_request_count = None
    _image_error_count = None
    _image_duration_ms = None
    _image_fallback_count = None
    _image_serve_count = None
    _tts_request_count = None
    _tts_error_count = None
    _tts_duration_ms = None
    _audio_serve_count = None


def _attrs(provider: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    attributes: dict[str, Any] = {"provider": provider}
    if extra:
        attributes.update(extra)
    return attributes


def record_conversation_request(provider: str) -> None:
    if _request_count is not None:
        _request_count.add(1, _attrs(provider))


def record_conversation_error(provider: str, *, error_type: str) -> None:
    if _error_count is not None:
        _error_count.add(1, _attrs(provider, {"error_type": error_type}))


def record_conversation_duration(provider: str, duration_ms: float) -> None:
    if _duration_ms is not None:
        _duration_ms.record(duration_ms, _attrs(provider))


def record_conversation_fallback(provider: str, *, reason: str) -> None:
    if _fallback_count is not None:
        _fallback_count.add(1, _attrs(provider, {"reason": reason}))


def record_image_request(provider: str) -> None:
    if _image_request_count is not None:
        _image_request_count.add(1, _attrs(provider))


def record_image_error(provider: str, *, error_type: str) -> None:
    if _image_error_count is not None:
        _image_error_count.add(1, _attrs(provider, {"error_type": error_type}))


def record_image_duration(provider: str, duration_ms: float) -> None:
    if _image_duration_ms is not None:
        _image_duration_ms.record(duration_ms, _attrs(provider))


def record_image_fallback(provider: str, *, reason: str) -> None:
    if _image_fallback_count is not None:
        _image_fallback_count.add(1, _attrs(provider, {"reason": reason}))


def record_image_serve(*, found: bool) -> None:
    if _image_serve_count is not None:
        _image_serve_count.add(1, {"found": found})


def record_tts_request(provider: str) -> None:
    if _tts_request_count is not None:
        _tts_request_count.add(1, _attrs(provider))


def record_tts_error(provider: str, *, error_type: str) -> None:
    if _tts_error_count is not None:
        _tts_error_count.add(1, _attrs(provider, {"error_type": error_type}))


def record_tts_duration(provider: str, duration_ms: float) -> None:
    if _tts_duration_ms is not None:
        _tts_duration_ms.record(duration_ms, _attrs(provider))


def record_audio_serve(*, found: bool) -> None:
    if _audio_serve_count is not None:
        _audio_serve_count.add(1, {"found": found})
