from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..enums import MemoryType


@dataclass(frozen=True, slots=True)
class Memory:
    """A single piece of per-user memory (stored in MongoDB)."""

    memory_id: str
    user_id: str
    memory_type: MemoryType
    content: str
    created_at: datetime
    updated_at: datetime
    session_id: str | None = None
    confidence: float = 0.8
    source: str = "user_interaction"
    expires_at: datetime | None = None
