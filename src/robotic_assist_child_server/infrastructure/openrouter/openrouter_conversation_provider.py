"""OpenRouter conversation provider.

Uses OpenRouter's OpenAI-compatible chat completions endpoint and falls back to
the fake provider for operational failures. It never logs API keys,
Authorization headers, prompt bodies, or child input text.
"""
from __future__ import annotations

import time
from collections.abc import Sequence

import httpx
from opentelemetry import trace

from ...application.ports.conversation_provider import (
    ConversationMessage,
    ConversationRequest,
    ConversationResponse,
)
from ...infrastructure.telemetry.metrics import (
    record_conversation_duration,
    record_conversation_error,
    record_conversation_fallback,
    record_conversation_request,
)
from ...shared.logging import get_logger
from .conversation_response_parser import ConversationResponseParser
from .fake_conversation_provider import FakeConversationProvider

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class OpenRouterConversationProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        chat_model: str,
        chat_model_fallback: str,
        http_referer: str,
        app_title: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
        max_retries: int,
        fallback_to_fake: bool,
        fake_provider: FakeConversationProvider,
        http_client: httpx.AsyncClient | None = None,
        parser: ConversationResponseParser | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._endpoint = base_url.rstrip("/") + "/chat/completions"
        self._chat_model = chat_model
        self._chat_model_fallback = chat_model_fallback
        self._http_referer = http_referer
        self._app_title = app_title
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._fallback_to_fake = fallback_to_fake
        self._fake = fake_provider
        self._client = http_client
        self._owns_client = http_client is None
        self._parser = parser or ConversationResponseParser()

    async def generate(self, request: ConversationRequest) -> ConversationResponse:
        provider_name = "openrouter"
        record_conversation_request(provider_name)
        started = time.perf_counter()

        try:
            with tracer.start_as_current_span("conversation.provider.openrouter") as span:
                span.set_attribute("conversation.provider", provider_name)
                span.set_attribute("conversation.model", self._select_model(request))

                if not self._api_key:
                    record_conversation_error(provider_name, error_type="missing_api_key")
                    return await self._fallback(request, reason="missing_api_key")

                try:
                    parsed = await self._request_with_retries(request)
                except Exception as exc:
                    reason = self._safe_error_reason(exc)
                    record_conversation_error(provider_name, error_type=reason)
                    return await self._fallback(request, reason=reason)

                if (
                    not parsed.is_contract_valid
                    and parsed.fallback_reason == "invalid_json"
                    and self._fallback_to_fake
                ):
                    record_conversation_error(provider_name, error_type="invalid_json")
                    return await self._fallback(request, reason="invalid_json")
                return parsed.response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            record_conversation_duration(provider_name, elapsed_ms)

    async def _request_with_retries(self, request: ConversationRequest):
        last_error: Exception | None = None
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._post_chat_completion(request)
                if response.status_code in _TRANSIENT_STATUS_CODES:
                    last_error = httpx.HTTPStatusError(
                        f"transient OpenRouter status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    if attempt < max_attempts:
                        self._log_transient_error(attempt, response.status_code)
                        continue
                response.raise_for_status()
                content = self._extract_content(response.json())
                return self._parser.parse(content)
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
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                last_error = exc
                break

        raise last_error or RuntimeError("OpenRouter request failed")

    async def _post_chat_completion(
        self, request: ConversationRequest
    ) -> httpx.Response:
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        payload = {
            "model": self._select_model(request),
            "messages": [m for m in self._to_openrouter_messages(request)],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._http_referer,
            "X-Title": self._app_title,
        }

        try:
            return await client.post(self._endpoint, json=payload, headers=headers)
        finally:
            if self._owns_client:
                await client.aclose()

    def _to_openrouter_messages(
        self, request: ConversationRequest
    ) -> Sequence[dict[str, str]]:
        messages = request.messages or (
            ConversationMessage(role="system", content=request.system_prompt),
            ConversationMessage(role="user", content=request.user_text),
        )
        return [{"role": m.role, "content": m.content} for m in messages]

    def _select_model(self, request: ConversationRequest) -> str:
        detail = request.metadata.get("response_detail")
        if detail in {"elaborated", "elaborate", "detailed"}:
            return self._chat_model_fallback
        return self._chat_model

    @staticmethod
    def _extract_content(payload: dict) -> str:
        choices = payload["choices"]
        message = choices[0]["message"]
        content = message["content"]
        if not isinstance(content, str):
            raise ValueError("OpenRouter response content is not text")
        return content

    @staticmethod
    def _safe_error_reason(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"http_{exc.response.status_code}"
        if isinstance(exc, httpx.TimeoutException):
            return "timeout"
        return exc.__class__.__name__

    async def _fallback(
        self, request: ConversationRequest, *, reason: str
    ) -> ConversationResponse:
        record_conversation_fallback("openrouter", reason=reason)
        logger.warning(
            "OpenRouter conversation fallback",
            extra={
                "event_name": "conversation.provider.openrouter.fallback",
                "session_id": request.session_id,
                "user_id": request.user_id,
                "attributes": {"reason": reason},
            },
        )
        if not self._fallback_to_fake:
            return ConversationResponse(
                text="Vamos tentar de novo daqui a pouco?",
                expression="error",
                intent="fallback",
                image_prompt=None,
            )
        return await self._fake.generate(request)

    @staticmethod
    def _log_transient_error(attempt: int, status_code: int | str) -> None:
        logger.warning(
            "OpenRouter transient error, retrying",
            extra={
                "event_name": "conversation.provider.openrouter.retry",
                "attributes": {"attempt": attempt, "status_code": status_code},
            },
        )
