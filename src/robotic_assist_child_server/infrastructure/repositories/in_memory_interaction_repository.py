"""In-memory interaction repository for the MVP slice.

A PostgreSQL-backed adapter will replace this later, implementing the same
InteractionRepository port. Data is not persisted across restarts.
"""
from __future__ import annotations

import asyncio

from ...domain.entities import TextInteraction


class InMemoryInteractionRepository:
    def __init__(self) -> None:
        self._store: dict[str, TextInteraction] = {}
        self._order: list[str] = []
        self._lock = asyncio.Lock()

    async def save(self, interaction: TextInteraction) -> None:
        async with self._lock:
            if interaction.interaction_id not in self._store:
                self._order.append(interaction.interaction_id)
            self._store[interaction.interaction_id] = interaction

    async def get(self, interaction_id: str) -> TextInteraction | None:
        async with self._lock:
            return self._store.get(interaction_id)

    async def list_recent_by_session(
        self, session_id: str, *, limit: int = 8
    ) -> list[TextInteraction]:
        async with self._lock:
            interactions = [
                self._store[interaction_id]
                for interaction_id in self._order
                if (
                    interaction_id in self._store
                    and self._store[interaction_id].session_id == session_id
                )
            ]
            return interactions[-limit:]
