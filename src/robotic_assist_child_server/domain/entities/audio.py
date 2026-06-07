from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GeneratedAudio:
    """TTS audio generated for an interaction and stored temporarily."""

    audio_id: str
    audio_url: str
    content_type: str
    provider: str
    model: str
    created_at: datetime
    duration_ms: int | None = None
    expires_at: datetime | None = None
    storage_path: str | None = None
