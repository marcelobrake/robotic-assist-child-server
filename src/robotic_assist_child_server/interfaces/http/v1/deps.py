from __future__ import annotations

from fastapi import Request

from ....config.providers import Container


def get_container(request: Request) -> Container:
    return request.app.state.container
