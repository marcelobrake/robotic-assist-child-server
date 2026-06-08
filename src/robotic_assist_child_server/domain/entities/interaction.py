from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .audio import GeneratedAudio
from .image import GeneratedImage
from ..enums import ClientType


@dataclass(frozen=True, slots=True)
class TextInteraction:
    """A single text interaction between a child and the assistant."""

    interaction_id: str
    session_id: str
    user_id: str
    client_type: ClientType
    input_text: str
    response_text: str
    created_at: datetime
    device_id: str | None = None
    expression: str = "happy"
    intent: str = "chat"
    image_prompt: str | None = None
    image: GeneratedImage | None = None
    audio: GeneratedAudio | None = None
    status: str = "accepted"
    ignored_reason: str | None = None
