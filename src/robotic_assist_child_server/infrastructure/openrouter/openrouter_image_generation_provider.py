"""OpenRouter image generation provider.

Uses OpenRouter's OpenAI-compatible chat completions endpoint for image-capable
models. It never logs API keys, Authorization headers, full prompts, or child
data. Generated image bytes are stored locally through ImageStoragePort.
"""
from __future__ import annotations

from io import BytesIO
import time

import httpx
from opentelemetry import trace
from PIL import Image, UnidentifiedImageError

from ...application.ports.image_generation import (
    ImageGenerationRequest,
    ImageStoragePort,
)
from ...domain.entities import GeneratedImage
from ...infrastructure.telemetry.metrics import (
    record_image_duration,
    record_image_error,
    record_image_fallback,
    record_image_request,
)
from ...shared.datetime import utc_now
from ...shared.ids import new_image_id
from ...shared.logging import get_logger
from .fake_image_generation_provider import FakeImageGenerationProvider
from .image_response_parser import ImageResponseParser, ParsedImageReference

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class OpenRouterImageGenerationProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        image_model: str,
        http_referer: str,
        app_title: str,
        timeout_seconds: float,
        max_retries: int,
        fallback_to_fake: bool,
        output_format: str,
        image_store: ImageStoragePort,
        fake_provider: FakeImageGenerationProvider,
        http_client: httpx.AsyncClient | None = None,
        parser: ImageResponseParser | None = None,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._endpoint = base_url.rstrip("/") + "/chat/completions"
        self._image_model = image_model
        self._http_referer = http_referer
        self._app_title = app_title
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._fallback_to_fake = fallback_to_fake
        self._output_format = output_format
        self._image_store = image_store
        self._fake = fake_provider
        self._client = http_client
        self._parser = parser or ImageResponseParser()

    async def generate(self, request: ImageGenerationRequest) -> GeneratedImage:
        provider_name = "openrouter"
        record_image_request(provider_name)
        started = time.perf_counter()

        with tracer.start_as_current_span("image.provider.openrouter") as span:
            span.set_attribute("image.provider", provider_name)
            span.set_attribute("image.model", self._image_model)
            span.set_attribute("image.aspect_ratio", request.aspect_ratio)
            span.set_attribute("image.size", request.size)

            if not self._api_key:
                record_image_error(provider_name, error_type="missing_api_key")
                return await self._fallback(request, reason="missing_api_key")

            client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
            try:
                try:
                    reference = await self._request_with_retries(client, request)
                    content, content_type = await self._materialize_reference(
                        client, reference
                    )
                    content_type = _validated_content_type(content, content_type)
                    content, content_type = _normalize_image_bytes(
                        content=content,
                        requested_size=request.size,
                        output_format=request.output_format or self._output_format,
                    )
                except Exception as exc:
                    reason = self._safe_error_reason(exc)
                    record_image_error(provider_name, error_type=reason)
                    return await self._fallback(request, reason=reason)

                image_id = new_image_id()
                path, image_url = self._image_store.save(
                    image_id=image_id,
                    content=content,
                    content_type=content_type,
                    output_format=request.output_format or self._output_format,
                )
                return GeneratedImage(
                    image_id=image_id,
                    image_url=image_url,
                    content_type=content_type,
                    provider=provider_name,
                    model=self._image_model,
                    prompt=request.prompt,
                    created_at=utc_now(),
                    expires_at=None,
                    storage_path=str(path),
                )
            finally:
                record_image_duration(provider_name, (time.perf_counter() - started) * 1000)
                if self._client is None:
                    await client.aclose()

    async def _request_with_retries(
        self, client: httpx.AsyncClient, request: ImageGenerationRequest
    ) -> ParsedImageReference:
        last_error: Exception | None = None
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._post_image_request(client, request)
                if response.status_code in _TRANSIENT_STATUS_CODES:
                    last_error = httpx.HTTPStatusError(
                        f"transient OpenRouter image status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    if attempt < max_attempts:
                        self._log_transient_error(attempt, response.status_code)
                        continue
                response.raise_for_status()
                return self._parser.parse(response.json())
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

        raise last_error or RuntimeError("OpenRouter image request failed")

    async def _post_image_request(
        self, client: httpx.AsyncClient, request: ImageGenerationRequest
    ) -> httpx.Response:
        prompt = (
            f"{request.prompt}\n\n"
            f"Requisitos de imagem: formato {request.aspect_ratio}, "
            f"tamanho desejado {request.size}."
        )
        payload = {
            "model": self._image_model,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
            "modalities": ["image", "text"],
            "image_config": {
                "aspect_ratio": request.aspect_ratio,
                "image_size": _gemini_image_size(request.size),
            },
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._http_referer,
            "X-Title": self._app_title,
        }
        return await client.post(self._endpoint, json=payload, headers=headers)

    async def _materialize_reference(
        self, client: httpx.AsyncClient, reference: ParsedImageReference
    ) -> tuple[bytes, str]:
        if reference.kind == "base64":
            content = self._parser.decode_base64(reference.value)
            return content, reference.content_type or _content_type_for_format(self._output_format)
        if reference.kind == "url":
            response = await client.get(reference.value)
            response.raise_for_status()
            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip()
                or reference.content_type
                or _content_type_for_format(self._output_format)
            )
            return response.content, content_type
        raise ValueError("Unsupported image reference")

    async def _fallback(
        self, request: ImageGenerationRequest, *, reason: str
    ) -> GeneratedImage:
        record_image_fallback("openrouter", reason=reason)
        logger.warning(
            "OpenRouter image fallback",
            extra={
                "event_name": "image.provider.openrouter.fallback",
                "session_id": request.session_id,
                "user_id": request.user_id,
                "attributes": {"reason": reason},
            },
        )
        if not self._fallback_to_fake:
            raise RuntimeError("OpenRouter image generation failed")
        return await self._fake.generate(request)

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
            "OpenRouter image transient error, retrying",
            extra={
                "event_name": "image.provider.openrouter.retry",
                "attributes": {"attempt": attempt, "status_code": status_code},
            },
        )


def _content_type_for_format(output_format: str) -> str:
    normalized = (output_format or "png").lower().lstrip(".")
    if normalized in {"jpg", "jpeg"}:
        return "image/jpeg"
    if normalized == "webp":
        return "image/webp"
    return "image/png"


def _validated_content_type(content: bytes, declared_content_type: str) -> str:
    detected = _detect_content_type(content)
    if detected is None:
        raise ValueError("OpenRouter image payload is not a supported image")
    declared = (declared_content_type or "").split(";")[0].strip().lower()
    if declared == detected:
        return declared
    return detected


def _normalize_image_bytes(
    *, content: bytes, requested_size: str, output_format: str
) -> tuple[bytes, str]:
    image_format = _pillow_format(output_format)
    try:
        with Image.open(BytesIO(content)) as source:
            source.load()
            target_size = _dimensions(requested_size) or source.size
            image = source
            if image.size != target_size:
                image = image.resize(target_size, Image.Resampling.LANCZOS)
            if image_format in {"JPEG", "PNG"} and image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            if image_format == "JPEG" and image.mode == "RGBA":
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format=image_format)
            return output.getvalue(), _content_type_for_format(output_format)
    except UnidentifiedImageError as exc:
        raise ValueError("OpenRouter image payload is not a supported image") from exc


def _dimensions(size: str) -> tuple[int, int] | None:
    normalized = (size or "").strip().lower()
    if "x" not in normalized:
        return None
    width_text, height_text = normalized.split("x", 1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return min(width, 4096), min(height, 4096)


def _pillow_format(output_format: str) -> str:
    normalized = (output_format or "png").strip().lower().lstrip(".")
    if normalized in {"jpg", "jpeg"}:
        return "JPEG"
    if normalized == "webp":
        return "WEBP"
    return "PNG"


def _detect_content_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _gemini_image_size(size: str) -> str:
    normalized = (size or "").strip().upper()
    if normalized in {"0.5K", "1K", "2K", "4K"}:
        return normalized
    if normalized in {"512X512", "512"}:
        return "0.5K"
    if normalized in {"2048X2048", "2048"}:
        return "2K"
    if normalized in {"4096X4096", "4096"}:
        return "4K"
    return "1K"
