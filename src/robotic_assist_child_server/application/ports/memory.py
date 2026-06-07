"""Memory ports (interfaces) for the MongoDB-backed memory system.

Concrete adapters: MongoMemoryRepository (infrastructure/mongodb),
SimpleMemoryRetriever and RuleBasedMemoryUpdater (application/services).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.entities import Memory


@runtime_checkable
class MemoryRepository(Protocol):
    """Persistence port for per-user memories."""

    async def save(self, memory: Memory) -> None: ...

    async def list_for_user(
        self, user_id: str, *, limit: int | None = None
    ) -> list[Memory]: ...


@runtime_checkable
class MemoryRetriever(Protocol):
    """Selects which memories to inject into the prompt for a user/session."""

    async def retrieve(
        self, user_id: str, session_id: str | None = None
    ) -> list[Memory]: ...


@runtime_checkable
class MemoryUpdater(Protocol):
    """Evaluates an interaction and creates/updates memories as needed."""

    async def evaluate(
        self, *, user_id: str, session_id: str | None, input_text: str
    ) -> list[Memory]: ...


@runtime_checkable
class MemoryPolicy(Protocol):
    """Decides whether a candidate memory should be stored."""

    def should_store(self, candidate: Memory) -> bool: ...
