from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Prompt:
    """A single prompt loaded from the prompts repository."""

    id: str
    path: str
    content: str
    content_hash: str
    loaded_at: datetime
    required: bool = False
