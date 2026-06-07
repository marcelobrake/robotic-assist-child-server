from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..enums import Role


@dataclass(frozen=True, slots=True)
class User:
    """A registered user (parent/admin/child/device).

    `password_hash` is populated when the record comes from the repository for
    authentication; it is never serialized to API responses.
    """

    id: str
    username: str
    role: Role
    created_at: datetime
    password_hash: str | None = None
