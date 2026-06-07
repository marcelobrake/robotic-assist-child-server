from __future__ import annotations

from ...domain.entities import Memory


class InMemoryMemoryRepository:
    """In-process MemoryRepository used for tests and when MongoDB is absent."""

    def __init__(self) -> None:
        self._items: list[Memory] = []

    async def save(self, memory: Memory) -> None:
        self._items = [m for m in self._items if m.memory_id != memory.memory_id]
        self._items.append(memory)

    async def list_for_user(
        self, user_id: str, *, limit: int | None = None
    ) -> list[Memory]:
        items = [m for m in self._items if m.user_id == user_id]
        items.sort(key=lambda m: m.created_at, reverse=True)
        return items[:limit] if limit is not None else items

    async def aclose(self) -> None:
        return None
