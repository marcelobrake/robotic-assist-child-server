"""PostgreSQL-backed user repository (also works on SQLite for dev/tests)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...domain.entities import User
from ...domain.enums import Role
from ..database.models import UserModel


class SqlAlchemyUserRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, user: User) -> None:
        async with self._session_factory() as session:
            session.add(
                UserModel(
                    id=user.id,
                    username=user.username,
                    password_hash=user.password_hash or "",
                    role=user.role.value,
                    created_at=user.created_at,
                )
            )
            await session.commit()

    async def get_by_username(self, username: str) -> User | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            return self._to_entity(result.scalar_one_or_none())

    async def get_by_id(self, user_id: str) -> User | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            return self._to_entity(result.scalar_one_or_none())

    @staticmethod
    def _to_entity(model: UserModel | None) -> User | None:
        if model is None:
            return None
        return User(
            id=model.id,
            username=model.username,
            role=Role(model.role),
            created_at=model.created_at,
            password_hash=model.password_hash,
        )
