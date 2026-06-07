"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config.providers import build_container
from .config.settings import Settings, get_settings
from .infrastructure.telemetry import init_telemetry
from .interfaces.http.v1 import build_v1_router
from .interfaces.websocket import build_ws_router
from .shared.logging import get_logger


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_telemetry(settings)
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = build_container(settings)
        try:
            container.prompt_loader.load_all()
        except Exception:  # pragma: no cover - startup logging
            logger.exception(
                "failed to load prompts on startup",
                extra={"event_name": "prompt.load_all"},
            )
        app.state.container = container
        app.state.settings = settings
        yield

    app = FastAPI(
        title="Robotic Assist Child Server",
        version=settings.service_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(build_v1_router())
    app.include_router(build_ws_router())
    return app
