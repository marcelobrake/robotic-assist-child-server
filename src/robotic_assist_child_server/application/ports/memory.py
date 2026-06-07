"""Memory ports (interfaces) prepared for the MongoDB-backed memory system.

Not implemented in the MVP slice; defined here so future use cases can depend
on stable contracts (MongoMemoryRepository, SimpleMemoryRetriever, ...).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryRepository(Protocol):
    async def save(self, memory: dict[str, Any]) -> None: ...
    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class MemoryRetriever(Protocol):
    async def retrieve(self, user_id: str, session_id: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class MemoryUpdater(Protocol):
    async def evaluate(self, user_id: str, session_id: str, interaction: dict[str, Any]) -> None: ...


@runtime_checkable
class MemoryPolicy(Protocol):
    def should_store(self, candidate: dict[str, Any]) -> bool: ...
