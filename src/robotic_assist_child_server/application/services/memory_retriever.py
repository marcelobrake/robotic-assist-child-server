"""Simple, non-vector memory retrieval.

Returns the most recent, non-expired memories for a user. No embeddings or
vector search (deferred) — just a recency-bounded fetch from the repository.
"""
from __future__ import annotations

from ...domain.entities import Memory
from ...shared.datetime import utc_now
from ..ports.memory import MemoryRepository


class SimpleMemoryRetriever:
    def __init__(self, repository: MemoryRepository, *, max_items: int = 10) -> None:
        self._repository = repository
        self._max_items = max_items

    async def retrieve(
        self, user_id: str, session_id: str | None = None
    ) -> list[Memory]:
        if not user_id:
            return []
        memories = await self._repository.list_for_user(user_id, limit=self._max_items)
        now = utc_now()
        return [m for m in memories if m.expires_at is None or m.expires_at > now]
