"""Minimal session WebSocket endpoint for the MVP slice.

Exists so the API Gateway WebSocket proxy has a real upstream. It reuses the
text interaction use case to return safe responses. Richer session/event
handling is left for future work.
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...application.use_cases import TextInteractionInput
from ...shared.errors import DomainError


def build_ws_router() -> APIRouter:
    router = APIRouter(prefix="/v1/ws")

    @router.websocket("/sessions/{session_id}")
    async def session_socket(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        container = websocket.app.state.container
        try:
            while True:
                text = await websocket.receive_text()
                try:
                    interaction = await container.handle_text_interaction.execute(
                        TextInteractionInput(text=text, session_id=session_id)
                    )
                    await websocket.send_json(
                        {
                            "interaction_id": interaction.interaction_id,
                            "session_id": interaction.session_id,
                            "response_text": interaction.response_text,
                        }
                    )
                except DomainError as exc:
                    await websocket.send_json({"error": exc.code, "message": exc.message})
        except WebSocketDisconnect:
            return

    return router
