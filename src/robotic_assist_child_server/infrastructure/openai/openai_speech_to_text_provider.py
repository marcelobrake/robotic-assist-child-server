"""OpenAI speech-to-text provider (optional, batch/cheaper).

Calls the OpenAI ``audio/transcriptions`` endpoint with the uploaded audio
bytes (multipart/form-data) using ``gpt-4o-mini-transcribe`` by default. It is
only constructed when ``STT_PROVIDER=openai``. It never logs the API key, the
Authorization header, or the audio bytes. Input audio is not stored.

On failure it raises; the caller decides how to surface the error.
"""
from __future__ import annotations

import time

import httpx
from opentelemetry import trace

from ...application.ports.speech import (
    SpeechTranscription,
    SpeechTranscriptionRequest,
)
from ...infrastructure.telemetry.metrics import (
    record_stt_duration,
    record_stt_error,
    record_stt_request,
)
from ...shared.logging import get_logger

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class OpenAISpeechToTextProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_retries: int = 2,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._client = http_client

    async def transcribe(
        self, request: SpeechTranscriptionRequest
    ) -> SpeechTranscription:
        provider_name = "openai"
        record_stt_request(provider_name)
        started = time.perf_counter()

        with tracer.start_as_current_span("stt.provider.openai") as span:
            span.set_attribute("stt.provider", provider_name)
            span.set_attribute("stt.model", self._model)

            if not self._api_key:
                record_stt_error(provider_name, error_type="missing_api_key")
                raise RuntimeError("OpenAI API key is not configured")

            client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
            try:
                try:
                    text = await self._request_with_retries(client, request)
                except Exception as exc:
                    record_stt_error(
                        provider_name, error_type=self._safe_error_reason(exc)
                    )
                    raise
                return SpeechTranscription(
                    text=text,
                    provider=provider_name,
                    model=self._model,
                    language=request.language,
                )
            finally:
                record_stt_duration(
                    provider_name, (time.perf_counter() - started) * 1000
                )
                if self._client is None:
                    await client.aclose()

    async def _request_with_retries(
        self, client: httpx.AsyncClient, request: SpeechTranscriptionRequest
    ) -> str:
        last_error: Exception | None = None
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._post_stt_request(client, request)
                if response.status_code in _TRANSIENT_STATUS_CODES:
                    last_error = httpx.HTTPStatusError(
                        f"transient OpenAI status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    if attempt < max_attempts:
                        self._log_transient_error(attempt, response.status_code)
                        continue
                response.raise_for_status()
                return self._extract_text(response)
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

        raise last_error or RuntimeError("OpenAI STT request failed")

    async def _post_stt_request(
        self, client: httpx.AsyncClient, request: SpeechTranscriptionRequest
    ) -> httpx.Response:
        endpoint = f"{self._base_url}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        data: dict[str, str] = {"model": self._model}
        if request.language:
            data["language"] = request.language
        files = {
            "file": (
                "audio",
                request.audio,
                request.content_type or "application/octet-stream",
            )
        }
        return await client.post(
            endpoint, headers=headers, data=data, files=files
        )

    @staticmethod
    def _extract_text(response: httpx.Response) -> str:
        payload = response.json()
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            raise ValueError("OpenAI returned no transcription text")
        return text.strip()

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
            "OpenAI STT transient error, retrying",
            extra={
                "event_name": "stt.provider.openai.retry",
                "attributes": {"attempt": attempt, "status_code": status_code},
            },
        )
