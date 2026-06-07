from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ....config.providers import Container
from ....domain.entities import User
from ....domain.enums import Role
from ....shared.datetime import utc_now
from ....shared.ids import DEV_USER_ID

# auto_error=False so endpoints can stay open (MVP / dev mode) when no token.
_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    return request.app.state.container


def _dev_user() -> User:
    return User(
        id=DEV_USER_ID,
        username=DEV_USER_ID,
        role=Role.PARENT,
        created_at=utc_now(),
    )


def _decode(container: Container, token: str) -> dict:
    try:
        return container.token_service.decode(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    container: Container = Depends(get_container),
) -> User:
    """Required authentication. In dev-bypass mode returns a synthetic user."""
    if container.settings.dev_auth_disabled:
        return _dev_user()
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória.",
        )
    payload = _decode(container, credentials.credentials)
    user = await container.user_repository.get_by_id(payload.get("sub", ""))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
        )
    return user


async def resolve_interaction_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    container: Container = Depends(get_container),
) -> str | None:
    """Optional auth for interactions.

    - dev-bypass: always returns the dev user id;
    - valid token: returns its subject;
    - invalid token: 401;
    - no token: None (anonymous, preserves the open MVP behavior).
    """
    if container.settings.dev_auth_disabled:
        return DEV_USER_ID
    if credentials is None:
        return None
    payload = _decode(container, credentials.credentials)
    return payload.get("sub")
