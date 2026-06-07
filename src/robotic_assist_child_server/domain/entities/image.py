from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    """Image generated for an interaction and stored temporarily."""

    image_id: str
    image_url: str
    content_type: str
    provider: str
    model: str
    prompt: str | None
    created_at: datetime
    expires_at: datetime | None = None
    storage_path: str | None = None
