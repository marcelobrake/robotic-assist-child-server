from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PasswordHasherPort(Protocol):
    """Port for hashing and verifying passwords (Argon2/bcrypt adapters)."""

    def hash(self, password: str) -> str:
        ...

    def verify(self, password_hash: str, password: str) -> bool:
        ...


@runtime_checkable
class TokenServicePort(Protocol):
    """Port for issuing and validating access tokens (JWT adapter)."""

    def create_access_token(self, *, subject: str, role: str) -> str:
        ...

    def decode(self, token: str) -> dict:
        ...
