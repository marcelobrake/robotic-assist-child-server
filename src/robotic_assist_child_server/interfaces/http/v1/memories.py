from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ....application.use_cases import CreateMemoryInput
from ....config.providers import Container
from ....domain.entities import Memory, User
from ....shared.datetime import to_rfc3339
from .deps import get_container, get_current_user
from .schemas import CreateMemoryRequest, MemoryListResponse, MemoryResponse

router = APIRouter(prefix="/memories", tags=["memories"])


def _to_response(memory: Memory) -> MemoryResponse:
    return MemoryResponse(
        memory_id=memory.memory_id,
        user_id=memory.user_id,
        session_id=memory.session_id,
        memory_type=memory.memory_type,
        content=memory.content,
        confidence=memory.confidence,
        source=memory.source,
        created_at=to_rfc3339(memory.created_at),
        updated_at=to_rfc3339(memory.updated_at),
        expires_at=to_rfc3339(memory.expires_at) if memory.expires_at else None,
    )


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    container: Container = Depends(get_container),
    current_user: User = Depends(get_current_user),
) -> MemoryListResponse:
    memories = await container.list_memories.execute(current_user.id)
    items = [_to_response(m) for m in memories]
    return MemoryListResponse(count=len(items), memories=items)


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: CreateMemoryRequest,
    container: Container = Depends(get_container),
    current_user: User = Depends(get_current_user),
) -> MemoryResponse:
    memory = await container.create_memory.execute(
        CreateMemoryInput(
            user_id=current_user.id,
            content=payload.content,
            memory_type=payload.memory_type,
            session_id=payload.session_id,
            confidence=payload.confidence,
            source=payload.source,
        )
    )
    return _to_response(memory)
