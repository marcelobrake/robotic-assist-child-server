"""MongoDB-backed MemoryRepository (collection: ``user_memories``).

No embeddings / no vector search — plain document storage and recency queries.
"""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from ...domain.entities import Memory
from ...domain.enums import MemoryType

_COLLECTION = "user_memories"


class MongoMemoryRepository:
    def __init__(self, client: AsyncIOMotorClient, database: str) -> None:
        self._client = client
        self._collection = client[database][_COLLECTION]

    async def save(self, memory: Memory) -> None:
        await self._collection.update_one(
            {"memory_id": memory.memory_id},
            {"$set": _to_doc(memory)},
            upsert=True,
        )

    async def list_for_user(
        self, user_id: str, *, limit: int | None = None
    ) -> list[Memory]:
        cursor = self._collection.find({"user_id": user_id}).sort("created_at", -1)
        if limit is not None:
            cursor = cursor.limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_to_entity(doc) for doc in docs]

    async def aclose(self) -> None:
        self._client.close()


def create_mongo_memory_repository(uri: str, database: str) -> MongoMemoryRepository:
    return MongoMemoryRepository(AsyncIOMotorClient(uri), database)


def _to_doc(memory: Memory) -> dict[str, Any]:
    return {
        "memory_id": memory.memory_id,
        "user_id": memory.user_id,
        "session_id": memory.session_id,
        "memory_type": memory.memory_type.value,
        "content": memory.content,
        "confidence": memory.confidence,
        "source": memory.source,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "expires_at": memory.expires_at,
    }


def _to_entity(doc: dict[str, Any]) -> Memory:
    return Memory(
        memory_id=doc["memory_id"],
        user_id=doc["user_id"],
        memory_type=MemoryType(doc.get("memory_type", "interest")),
        content=doc["content"],
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at", doc["created_at"]),
        session_id=doc.get("session_id"),
        confidence=doc.get("confidence", 0.8),
        source=doc.get("source", "user_interaction"),
        expires_at=doc.get("expires_at"),
    )
