from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_live_is_ok(client: TestClient) -> None:
    response = client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready_reports_prompts_loaded(client: TestClient) -> None:
    response = client.get("/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["prompts"] == "ok"


def test_health_startup_ok(client: TestClient) -> None:
    response = client.get("/v1/health/startup")
    assert response.status_code == 200
    assert response.json()["status"] == "started"


def test_version_endpoint(client: TestClient) -> None:
    response = client.get("/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert body["service_name"] == "robotic-assist-child-server"
    assert body["service_version"]
