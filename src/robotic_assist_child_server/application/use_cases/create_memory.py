from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities import Memory
from ...domain.enums import MemoryType
from ...shared.datetime import utc_now
from ...shared.ids import new_memory_id
from ..ports.memory import MemoryRepository


@dataclass(frozen=True, slots=True)
class CreateMemoryInput:
    user_id: str
    content: str
    memory_type: MemoryType = MemoryType.INTEREST
    session_id: str | None = None
    confidence: float = 0.8
    source: str = "manual"


class CreateMemory:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def execute(self, data: CreateMemoryInput) -> Memory:
        now = utc_now()
        memory = Memory(
            memory_id=new_memory_id(),
            user_id=data.user_id,
            session_id=data.session_id,
            memory_type=data.memory_type,
            content=data.content.strip(),
            confidence=data.confidence,
            source=data.source,
            created_at=now,
            updated_at=now,
        )
        await self._repository.save(memory)
        return memory
