from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from opentelemetry import trace

from ....config.providers import Container
from ....infrastructure.telemetry.metrics import record_image_serve
from .deps import get_container

router = APIRouter(prefix="/images", tags=["images"])
tracer = trace.get_tracer(__name__)


@router.get("/{image_id}")
async def get_image(
    image_id: str, container: Container = Depends(get_container)
) -> FileResponse:
    with tracer.start_as_current_span("image.serve") as span:
        span.set_attribute("image.id", image_id)
        stored = container.image_store.resolve(image_id)
        span.set_attribute("image.found", stored is not None)
        record_image_serve(found=stored is not None)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Imagem não encontrada.",
            )
        return FileResponse(path=stored.path, media_type=stored.content_type)
