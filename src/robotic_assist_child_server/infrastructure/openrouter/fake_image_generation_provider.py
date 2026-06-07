"""Fake image provider for local tests and development."""
from __future__ import annotations

import struct
import time
import zlib

from opentelemetry import trace

from ...application.ports.image_generation import (
    ImageGenerationRequest,
    ImageStoragePort,
)
from ...domain.entities import GeneratedImage
from ...infrastructure.telemetry.metrics import (
    record_image_duration,
    record_image_request,
)
from ...shared.datetime import utc_now
from ...shared.ids import new_image_id

tracer = trace.get_tracer(__name__)


class FakeImageGenerationProvider:
    def __init__(
        self,
        *,
        image_store: ImageStoragePort,
        model: str = "fake-image-placeholder",
    ) -> None:
        self._image_store = image_store
        self._model = model

    async def generate(self, request: ImageGenerationRequest) -> GeneratedImage:
        started = time.perf_counter()
        provider_name = "fake"
        record_image_request(provider_name)

        with tracer.start_as_current_span("image.provider.fake") as span:
            span.set_attribute("image.provider", provider_name)
            span.set_attribute("image.model", self._model)
            image_id = new_image_id()
            width, height = _size_from_request(request.size)
            content = _placeholder_png(width=width, height=height)
            content_type = "image/png"
            path, image_url = self._image_store.save(
                image_id=image_id,
                content=content,
                content_type=content_type,
                output_format=request.output_format,
            )
            record_image_duration(provider_name, (time.perf_counter() - started) * 1000)
            return GeneratedImage(
                image_id=image_id,
                image_url=image_url,
                content_type=content_type,
                provider=provider_name,
                model=self._model,
                prompt=request.prompt,
                created_at=utc_now(),
                expires_at=None,
                storage_path=str(path),
            )


def _placeholder_png(width: int = 64, height: int = 64) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            if (x // 8 + y // 8) % 2 == 0:
                row.extend((79, 170, 255))
            else:
                row.extend((255, 214, 102))
        rows.append(bytes(row))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, level=9))
        + _chunk(b"IEND", b"")
    )


def _chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _size_from_request(size: str) -> tuple[int, int]:
    normalized = (size or "800x800").strip().lower()
    if "x" not in normalized:
        return 800, 800
    width_text, height_text = normalized.split("x", 1)
    try:
        width = max(1, min(2048, int(width_text)))
        height = max(1, min(2048, int(height_text)))
    except ValueError:
        return 800, 800
    return width, height
