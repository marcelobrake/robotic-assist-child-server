from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ...domain.entities import GeneratedImage


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    prompt: str
    session_id: str
    user_id: str
    aspect_ratio: str = "1:1"
    size: str = "800x800"
    output_format: str = "png"
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class ImageGenerationProvider(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> GeneratedImage:
        ...


@dataclass(frozen=True, slots=True)
class StoredImage:
    path: Path
    content_type: str


@runtime_checkable
class ImageStoragePort(Protocol):
    def save(
        self, *, image_id: str, content: bytes, content_type: str, output_format: str
    ) -> tuple[Path, str]:
        ...

    def resolve(self, image_id: str) -> StoredImage | None:
        ...
