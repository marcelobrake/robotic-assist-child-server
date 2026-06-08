from __future__ import annotations

import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from ....application.use_cases import AudioInteractionInput, TextInteractionInput
from ....config.providers import Container
from ....domain.entities import GeneratedAudio, GeneratedImage, TextInteraction
from ....domain.enums import ClientType
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

# Audio container/codec MIME types accepted by the audio endpoint.
_ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/aac",
    "audio/ogg",
    "audio/m4a",
    "audio/x-m4a",
}


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


def _interaction_response(interaction: TextInteraction) -> TextInteractionResponse:
    is_ignored = interaction.status == "ignored"
    return TextInteractionResponse(
        interaction_id=interaction.interaction_id,
        session_id=interaction.session_id,
        user_id=interaction.user_id,
        client_type=interaction.client_type,
        input_text=interaction.input_text,
        response_text=interaction.response_text,
        assistant_text=None if is_ignored else interaction.response_text,
        expression=interaction.expression,
        intent=interaction.intent,
        image_prompt=interaction.image_prompt,
        image=_image_response(interaction.image),
        audio=_audio_response(interaction.audio),
        status=interaction.status,
        ignored_reason=interaction.ignored_reason,
        created_at=to_rfc3339(interaction.created_at),
        device_id=interaction.device_id,
    )


def _parse_metadata(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metadata deve ser um objeto JSON válido.",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metadata deve ser um objeto JSON.",
        )
    return {str(key): str(value) for key, value in parsed.items()}


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

    return _interaction_response(interaction)


@router.post("/audio", response_model=TextInteractionResponse)
async def create_audio_interaction(
    container: Container = Depends(get_container),
    resolved_user_id: str | None = Depends(resolve_interaction_user_id),
    audio_file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    client_type: ClientType = Form(default=ClientType.UNKNOWN),
    device_id: str | None = Form(default=None),
    generate_audio: bool = Form(default=False),
    listener_mode: bool = Form(default=False),
    language: str | None = Form(default=None),
    metadata: str | None = Form(default=None),
) -> TextInteractionResponse:
    content_type = (audio_file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de áudio não suportado: {content_type or 'desconhecido'}.",
        )

    audio_bytes = await audio_file.read()
    await audio_file.close()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo de áudio vazio.",
        )
    max_bytes = container.settings.max_audio_upload_bytes
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "Áudio excede o tamanho máximo de "
                f"{container.settings.max_audio_upload_mb} MB."
            ),
        )

    parsed_metadata = _parse_metadata(metadata)

    try:
        interaction = await container.handle_audio_interaction.execute(
            AudioInteractionInput(
                audio=audio_bytes,
                content_type=content_type,
                session_id=session_id,
                user_id=resolved_user_id or user_id,
                client_type=client_type,
                device_id=device_id,
                generate_audio=generate_audio,
                listener_mode=listener_mode,
                language=language,
                metadata=parsed_metadata,
            )
        )
    except DomainError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc

    return _interaction_response(interaction)
