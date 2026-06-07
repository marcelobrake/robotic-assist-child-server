from __future__ import annotations

from ...domain.entities import Memory
from ..ports.memory import MemoryRepository


class ListMemories:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: str, *, limit: int | None = None) -> list[Memory]:
        if not user_id:
            return []
        return await self._repository.list_for_user(user_id, limit=limit)
