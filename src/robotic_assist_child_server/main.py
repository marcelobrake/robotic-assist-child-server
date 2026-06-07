"""Entrypoint. Exposes `app` for uvicorn and supports `python -m`."""
from __future__ import annotations

import uvicorn

from .app import create_app
from .config.settings import get_settings

app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "robotic_assist_child_server.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
