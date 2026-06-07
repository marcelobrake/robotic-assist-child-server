from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ....application.use_cases import AuthenticateUserInput, RegisterUserInput
from ....config.providers import Container
from ....domain.entities import User
from ....shared.datetime import to_rfc3339
from ....shared.errors import DomainError
from .deps import get_container, get_current_user
from .schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        user_id=user.id,
        username=user.username,
        role=user.role,
        created_at=to_rfc3339(user.created_at),
    )


def _token_response(container: Container, user: User) -> TokenResponse:
    access_token = container.token_service.create_access_token(
        subject=user.id, role=user.role.value
    )
    return TokenResponse(access_token=access_token, user=_user_response(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    container: Container = Depends(get_container),
) -> TokenResponse:
    try:
        user = await container.register_user.execute(
            RegisterUserInput(
                username=payload.username,
                password=payload.password,
                role=payload.role,
            )
        )
    except DomainError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc
    return _token_response(container, user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    container: Container = Depends(get_container),
) -> TokenResponse:
    try:
        user = await container.authenticate_user.execute(
            AuthenticateUserInput(username=payload.username, password=payload.password)
        )
    except DomainError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc
    return _token_response(container, user)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(current_user)
