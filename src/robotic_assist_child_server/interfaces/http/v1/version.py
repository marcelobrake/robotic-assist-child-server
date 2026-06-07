from __future__ import annotations

from fastapi import APIRouter, Depends

from ....config.providers import Container
from .deps import get_container
from .schemas import VersionResponse

router = APIRouter(tags=["version"])


@router.get("/version", response_model=VersionResponse)
def version(container: Container = Depends(get_container)) -> VersionResponse:
    settings = container.settings
    return VersionResponse(
        service_name=settings.service_name,
        service_version=settings.service_version,
        deployment_environment=settings.deployment_environment,
    )
