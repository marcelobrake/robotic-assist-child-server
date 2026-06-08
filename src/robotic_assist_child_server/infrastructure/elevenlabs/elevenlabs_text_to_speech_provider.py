"""ElevenLabs text-to-speech provider.

Calls the ElevenLabs ``text-to-speech`` endpoint and stores the returned audio
bytes locally through ``AudioStoragePort``. It never logs the API key, the
Authorization/``xi-api-key`` header, audio bytes, or the child's text.

On failure it raises; the caller (HandleTextInteraction) treats audio as a
best-effort enhancement so the textual reply is never broken by a TTS error.
"""
from __future__ import annotations

import time

import httpx
from opentelemetry import trace

from ...application.ports.speech import AudioStoragePort, SpeechSynthesisRequest
from ...domain.entities import GeneratedAudio
from ...infrastructure.audio import content_type_for_format
from ...infrastructure.telemetry.metrics import (
    record_tts_duration,
    record_tts_error,
    record_tts_request,
)
from ...shared.datetime import utc_now
from ...shared.ids import new_audio_id
from ...shared.logging import get_logger

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
_MIN_SPEED = 0.7
_MAX_SPEED = 1.2

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


def _clamp_speed(speed: float) -> float:
    return min(max(speed, _MIN_SPEED), _MAX_SPEED)


class ElevenLabsTextToSpeechProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        voice_id: str | None,
        model: str,
        output_format: str,
        timeout_seconds: float,
        max_retries: int,
        audio_store: AudioStoragePort,
        speed: float = 1.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._voice_id = voice_id.strip() if voice_id else None
        self._model = model
        self._output_format = output_format
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._speed = _clamp_speed(speed)
        self._audio_store = audio_store
        self._client = http_client

    async def synthesize(self, request: SpeechSynthesisRequest) -> GeneratedAudio:
        provider_name = "elevenlabs"
        record_tts_request(provider_name)
        started = time.perf_counter()

        with tracer.start_as_current_span("tts.provider.elevenlabs") as span:
            span.set_attribute("tts.provider", provider_name)
            span.set_attribute("tts.model", self._model)
            voice_id = request.voice_id or self._voice_id
            output_format = request.output_format or self._output_format
            span.set_attribute("tts.output_format", output_format)

            if not self._api_key:
                record_tts_error(provider_name, error_type="missing_api_key")
                raise RuntimeError("ElevenLabs API key is not configured")
            if not voice_id:
                record_tts_error(provider_name, error_type="missing_voice_id")
                raise RuntimeError("ElevenLabs voice id is not configured")

            client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
            try:
                try:
                    content = await self._request_with_retries(
                        client, request, voice_id, output_format
                    )
                except Exception as exc:
                    record_tts_error(
                        provider_name, error_type=self._safe_error_reason(exc)
                    )
                    raise

                content_type = content_type_for_format(output_format)
                audio_id = new_audio_id()
                path, audio_url = self._audio_store.save(
                    audio_id=audio_id,
                    content=content,
                    content_type=content_type,
                    output_format=output_format,
                )
                return GeneratedAudio(
                    audio_id=audio_id,
                    audio_url=audio_url,
                    content_type=content_type,
                    provider=provider_name,
                    model=self._model,
                    created_at=utc_now(),
                    duration_ms=None,
                    expires_at=None,
                    storage_path=str(path),
                )
            finally:
                record_tts_duration(
                    provider_name, (time.perf_counter() - started) * 1000
                )
                if self._client is None:
                    await client.aclose()

    async def _request_with_retries(
        self,
        client: httpx.AsyncClient,
        request: SpeechSynthesisRequest,
        voice_id: str,
        output_format: str,
    ) -> bytes:
        last_error: Exception | None = None
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._post_tts_request(
                    client, request, voice_id, output_format
                )
                if response.status_code in _TRANSIENT_STATUS_CODES:
                    last_error = httpx.HTTPStatusError(
                        f"transient ElevenLabs status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    if attempt < max_attempts:
                        self._log_transient_error(attempt, response.status_code)
                        continue
                response.raise_for_status()
                if not response.content:
                    raise ValueError("ElevenLabs returned an empty audio payload")
                return response.content
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < max_attempts:
                    self._log_transient_error(attempt, "timeout")
                    continue
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code in _TRANSIENT_STATUS_CODES and attempt < max_attempts:
                    self._log_transient_error(attempt, status_code)
                    continue
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                break

        raise last_error or RuntimeError("ElevenLabs TTS request failed")

    async def _post_tts_request(
        self,
        client: httpx.AsyncClient,
        request: SpeechSynthesisRequest,
        voice_id: str,
        output_format: str,
    ) -> httpx.Response:
        endpoint = f"{self._base_url}/v1/text-to-speech/{voice_id}"
        payload = {
            "text": request.text,
            "model_id": self._model,
            "voice_settings": {"speed": self._speed},
        }
        headers = {
            "xi-api-key": self._api_key or "",
            "Content-Type": "application/json",
            "Accept": "audio/*",
        }
        params = {"output_format": output_format}
        return await client.post(
            endpoint, json=payload, headers=headers, params=params
        )

    @staticmethod
    def _safe_error_reason(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"http_{exc.response.status_code}"
        if isinstance(exc, httpx.TimeoutException):
            return "timeout"
        return exc.__class__.__name__

    @staticmethod
    def _log_transient_error(attempt: int, status_code: int | str) -> None:
        logger.warning(
            "ElevenLabs transient error, retrying",
            extra={
                "event_name": "tts.provider.elevenlabs.retry",
                "attributes": {"attempt": attempt, "status_code": status_code},
            },
        )
