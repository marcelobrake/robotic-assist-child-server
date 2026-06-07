from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.entities import TextInteraction


@runtime_checkable
class InteractionRepository(Protocol):
    """Port for persisting interactions (PostgreSQL adapter in future)."""

    async def save(self, interaction: TextInteraction) -> None:
        ...

    async def get(self, interaction_id: str) -> TextInteraction | None:
        ...
