from __future__ import annotations

from fastapi.testclient import TestClient


def test_text_interaction_returns_safe_response(client: TestClient) -> None:
    response = client.post("/v1/interactions/text", json={"text": "Oi Cubinho!"})
    assert response.status_code == 200
    body = response.json()
    assert body["interaction_id"].startswith("int_")
    assert body["session_id"].startswith("session_")
    assert body["response_text"]
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
