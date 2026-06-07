from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from opentelemetry import trace

from ....config.providers import Container
from ....infrastructure.telemetry.metrics import record_audio_serve
from .deps import get_container

router = APIRouter(prefix="/audio", tags=["audio"])
tracer = trace.get_tracer(__name__)


@router.get("/{audio_id}")
async def get_audio(
    audio_id: str, container: Container = Depends(get_container)
) -> FileResponse:
    with tracer.start_as_current_span("audio.serve") as span:
        span.set_attribute("audio.id", audio_id)
        stored = container.audio_store.resolve(audio_id)
        span.set_attribute("audio.found", stored is not None)
        record_audio_serve(found=stored is not None)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Áudio não encontrado.",
            )
        return FileResponse(path=stored.path, media_type=stored.content_type)
