"""JWT access-token service (implements TokenServicePort).

Refresh tokens are intentionally not implemented yet.
"""
from __future__ import annotations

from datetime import timedelta

import jwt

from ...shared.datetime import utc_now


class JwtService:
    def __init__(self, *, secret: str, algorithm: str, expires_minutes: int) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._expires = timedelta(minutes=expires_minutes)

    def create_access_token(self, *, subject: str, role: str) -> str:
        now = utc_now()
        payload = {
            "sub": subject,
            "role": role,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + self._expires).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> dict:
        return jwt.decode(token, self._secret, algorithms=[self._algorithm])
