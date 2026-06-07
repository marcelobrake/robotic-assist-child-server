from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.entities import User


@runtime_checkable
class UserRepository(Protocol):
    """Port for persisting and querying users."""

    async def create(self, user: User) -> None:
        ...

    async def get_by_username(self, username: str) -> User | None:
        ...

    async def get_by_id(self, user_id: str) -> User | None:
        ...
