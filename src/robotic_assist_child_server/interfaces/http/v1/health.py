from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from ....config.providers import Container
from .deps import get_container
from .schemas import HealthStatus

router = APIRouter(prefix="/health", tags=["health"])

# Checks for databases are prepared but reported as "skipped" in the MVP slice,
# since the vertical slice does not depend on them yet.
_DB_CHECKS = {"postgres": "skipped", "mongodb": "skipped", "redis": "skipped"}


@router.get("/live", response_model=HealthStatus)
def live() -> HealthStatus:
    # Liveness must not depend on external systems.
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus)
def ready(
    response: Response,
    container: Container = Depends(get_container),
) -> HealthStatus:
    prompts_loaded = container.prompt_loader.is_loaded()
    checks = {
        "config": "ok",
        "prompts": "ok" if prompts_loaded else "not_loaded",
        **_DB_CHECKS,
    }
    ready_state = prompts_loaded
    if not ready_state:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthStatus(status="ready" if ready_state else "not_ready", checks=checks)


@router.get("/startup", response_model=HealthStatus)
def startup(
    response: Response,
    container: Container = Depends(get_container),
) -> HealthStatus:
    prompts_loaded = container.prompt_loader.is_loaded()
    checks = {
        "config": "ok",
        "prompts": "ok" if prompts_loaded else "not_loaded",
        "telemetry": "ok",
        "migrations": "skipped",
        "workers": "ok",
    }
    started = prompts_loaded
    if not started:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthStatus(status="started" if started else "starting", checks=checks)


@router.get("", response_model=HealthStatus)
def health(container: Container = Depends(get_container)) -> HealthStatus:
    return HealthStatus(
        status="ok",
        checks={"prompts": "ok" if container.prompt_loader.is_loaded() else "not_loaded"},
    )
