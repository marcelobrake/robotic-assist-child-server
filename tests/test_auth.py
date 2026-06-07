from __future__ import annotations

from fastapi.testclient import TestClient


def _register(client: TestClient, username: str = "parent_ana", password: str = "s3cret!") -> dict:
    response = client.post(
        "/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_returns_token_and_user(client: TestClient) -> None:
    body = _register(client)
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "parent_ana"
    assert body["user"]["user_id"].startswith("usr_")
    assert body["user"]["role"] == "parent"
    assert body["user"]["created_at"].endswith("Z")


def test_register_duplicate_username_conflicts(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/v1/auth/register",
        json={"username": "parent_ana", "password": "another"},
    )
    assert response.status_code == 409


def test_login_with_valid_credentials(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/v1/auth/login",
        json={"username": "parent_ana", "password": "s3cret!"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_invalid_credentials(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/v1/auth/login",
        json={"username": "parent_ana", "password": "wrong"},
    )
    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    token = _register(client)["access_token"]
    response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "parent_ana"


def test_authenticated_interaction_uses_token_subject(client: TestClient) -> None:
    auth = _register(client)
    token = auth["access_token"]
    user_id = auth["user"]["user_id"]
    response = client.post(
        "/v1/interactions/text",
        json={"text": "Oi Cubinho!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == user_id


def test_dev_mode_interaction_uses_dev_user(dev_client: TestClient) -> None:
    response = dev_client.post("/v1/interactions/text", json={"text": "Oi Cubinho!"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "dev_user"
