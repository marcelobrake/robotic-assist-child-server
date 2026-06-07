from __future__ import annotations

from fastapi.testclient import TestClient


def test_text_interaction_returns_safe_response(client: TestClient) -> None:
    response = client.post("/v1/interactions/text", json={"text": "Oi Cubinho!"})
    assert response.status_code == 200
    body = response.json()
    assert body["interaction_id"].startswith("int_")
    assert body["session_id"].startswith("session_")
    assert body["response_text"]
    assert body["assistant_text"] == body["response_text"]
    assert body["expression"] == "happy"
    assert body["intent"] == "chat"
    assert body["status"] == "accepted"
    assert body["input_text"] == "Oi Cubinho!"
    assert body["created_at"].endswith("Z")


def test_text_interaction_preserves_session_id(client: TestClient) -> None:
    response = client.post(
        "/v1/interactions/text",
        json={"text": "Vamos brincar?", "session_id": "session_abc"},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == "session_abc"


def test_unsafe_request_is_redirected(client: TestClient) -> None:
    response = client.post(
        "/v1/interactions/text",
        json={"text": "Qual é a sua senha?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "gente grande" in body["response_text"]


def test_empty_text_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/interactions/text", json={"text": ""})
    assert response.status_code == 422


def test_text_interaction_accepts_input_text_contract(client: TestClient) -> None:
    response = client.post(
        "/v1/interactions/text",
        json={
            "session_id": "session_local",
            "client_type": "test",
            "input_text": "Oi Cubinho!",
            "metadata": {"device_id": "local_test", "locale": "pt-BR"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["input_text"] == "Oi Cubinho!"
    assert body["device_id"] == "local_test"
    assert body["client_type"] == "test"


def test_text_interaction_uses_configured_openrouter_provider_without_key(
    settings,
) -> None:
    from fastapi.testclient import TestClient

    from robotic_assist_child_server.app import create_app
    from robotic_assist_child_server.infrastructure.openrouter import (
        OpenRouterConversationProvider,
    )

    settings.conversation_provider = "openrouter"
    settings.openrouter_api_key = None
    app = create_app(settings)
    with TestClient(app) as test_client:
        assert isinstance(
            app.state.container.conversation_provider,
            OpenRouterConversationProvider,
        )
        response = test_client.post("/v1/interactions/text", json={"text": "Oi!"})

    assert response.status_code == 200
    assert response.json()["response_text"]
