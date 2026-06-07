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
        self._lock = asyncio.Lock()

    async def save(self, interaction: TextInteraction) -> None:
        async with self._lock:
            self._store[interaction.interaction_id] = interaction

    async def get(self, interaction_id: str) -> TextInteraction | None:
        async with self._lock:
            return self._store.get(interaction_id)
