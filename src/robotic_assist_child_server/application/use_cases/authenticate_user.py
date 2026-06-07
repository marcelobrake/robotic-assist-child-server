from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities import User
from ...shared.errors import InvalidCredentialsError
from ..ports.security import PasswordHasherPort
from ..ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class AuthenticateUserInput:
    username: str
    password: str


class AuthenticateUser:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        password_hasher: PasswordHasherPort,
    ) -> None:
        self._users = user_repository
        self._hasher = password_hasher

    async def execute(self, data: AuthenticateUserInput) -> User:
        user = await self._users.get_by_username(data.username.strip())
        if user is None or not user.password_hash:
            raise InvalidCredentialsError("Usuário ou senha inválidos.")
        if not self._hasher.verify(user.password_hash, data.password):
            raise InvalidCredentialsError("Usuário ou senha inválidos.")
        return user
