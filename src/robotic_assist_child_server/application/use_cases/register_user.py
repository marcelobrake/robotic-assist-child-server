from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities import User
from ...domain.enums import Role
from ...shared.datetime import utc_now
from ...shared.errors import UserAlreadyExistsError
from ...shared.ids import new_user_id
from ..ports.security import PasswordHasherPort
from ..ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class RegisterUserInput:
    username: str
    password: str
    role: Role = Role.PARENT


class RegisterUser:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        password_hasher: PasswordHasherPort,
    ) -> None:
        self._users = user_repository
        self._hasher = password_hasher

    async def execute(self, data: RegisterUserInput) -> User:
        username = data.username.strip()
        existing = await self._users.get_by_username(username)
        if existing is not None:
            raise UserAlreadyExistsError(f"Usuário '{username}' já existe.")

        user = User(
            id=new_user_id(),
            username=username,
            role=data.role,
            created_at=utc_now(),
            password_hash=self._hasher.hash(data.password),
        )
        await self._users.create(user)
        return user
