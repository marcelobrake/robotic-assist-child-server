from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ....application.use_cases import TextInteractionInput
from ....config.providers import Container
from ....shared.datetime import to_rfc3339
from ....shared.errors import DomainError
from .deps import get_container
from .schemas import TextInteractionRequest, TextInteractionResponse

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.post("/text", response_model=TextInteractionResponse)
async def create_text_interaction(
    payload: TextInteractionRequest,
    container: Container = Depends(get_container),
) -> TextInteractionResponse:
    try:
        interaction = await container.handle_text_interaction.execute(
            TextInteractionInput(
                text=payload.text,
                session_id=payload.session_id,
                user_id=payload.user_id,
                client_type=payload.client_type,
                device_id=payload.device_id,
            )
        )
    except DomainError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc

    return TextInteractionResponse(
        interaction_id=interaction.interaction_id,
        session_id=interaction.session_id,
        user_id=interaction.user_id,
        client_type=interaction.client_type,
        input_text=interaction.input_text,
        response_text=interaction.response_text,
        created_at=to_rfc3339(interaction.created_at),
        device_id=interaction.device_id,
    )
