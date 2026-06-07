from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ....application.use_cases import TextInteractionInput
from ....config.providers import Container
from ....domain.entities import GeneratedAudio, GeneratedImage
from ....shared.datetime import to_rfc3339
from ....shared.errors import DomainError
from .deps import get_container, resolve_interaction_user_id
from .schemas import (
    GeneratedAudioResponse,
    GeneratedImageResponse,
    TextInteractionRequest,
    TextInteractionResponse,
)

router = APIRouter(prefix="/interactions", tags=["interactions"])


def _image_response(image: GeneratedImage | None) -> GeneratedImageResponse | None:
    if image is None:
        return None
    return GeneratedImageResponse(
        image_id=image.image_id,
        image_url=image.image_url,
        content_type=image.content_type,
        provider=image.provider,
        model=image.model,
        created_at=to_rfc3339(image.created_at),
        expires_at=to_rfc3339(image.expires_at) if image.expires_at else None,
    )


def _audio_response(audio: GeneratedAudio | None) -> GeneratedAudioResponse | None:
    if audio is None:
        return None
    return GeneratedAudioResponse(
        audio_id=audio.audio_id,
        audio_url=audio.audio_url,
        content_type=audio.content_type,
        duration_ms=audio.duration_ms,
        provider=audio.provider,
        model=audio.model,
        created_at=to_rfc3339(audio.created_at),
        expires_at=to_rfc3339(audio.expires_at) if audio.expires_at else None,
    )


@router.post("/text", response_model=TextInteractionResponse)
async def create_text_interaction(
    payload: TextInteractionRequest,
    container: Container = Depends(get_container),
    resolved_user_id: str | None = Depends(resolve_interaction_user_id),
) -> TextInteractionResponse:
    try:
        interaction = await container.handle_text_interaction.execute(
            TextInteractionInput(
                text=payload.text,
                session_id=payload.session_id,
                user_id=resolved_user_id or payload.user_id,
                client_type=payload.client_type,
                device_id=payload.device_id,
                generate_audio=payload.generate_audio,
                metadata=payload.metadata,
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
        assistant_text=interaction.response_text,
        expression=interaction.expression,
        intent=interaction.intent,
        image_prompt=interaction.image_prompt,
        image=_image_response(interaction.image),
        audio=_audio_response(interaction.audio),
        status=interaction.status,
        created_at=to_rfc3339(interaction.created_at),
        device_id=interaction.device_id,
    )
