from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from robotic_assist_child_server.application.services import PromptComposer
from robotic_assist_child_server.infrastructure.prompts import FilePromptLoader


FIXTURE_PROMPTS = Path(__file__).parent / "fixtures" / "prompts"


def test_list_prompts_loaded_from_manifest(client: TestClient) -> None:
    response = client.get("/v1/prompts")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5
    ids = {p["id"] for p in body["prompts"]}
    assert "system.child_robot_base" in ids
    assert "interaction.image_generation" in ids
    for prompt in body["prompts"]:
        assert prompt["content_hash"]
        assert prompt["loaded_at"].endswith("Z")


def test_get_single_prompt_includes_content(client: TestClient) -> None:
    response = client.get("/v1/prompts/system.child_robot_base")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "system.child_robot_base"
    assert "Cubinho" in body["content"]


def test_get_unknown_prompt_returns_404(client: TestClient) -> None:
    response = client.get("/v1/prompts/does.not.exist")
    assert response.status_code == 404


def test_reload_prompts(client: TestClient) -> None:
    response = client.post("/v1/prompts/reload")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reloaded"
    assert body["count"] == 5
    # Prompts must still be listable after reload (no restart required).
    assert client.get("/v1/prompts").json()["count"] == 5


def test_prompt_composer_includes_image_generation_prompt() -> None:
    loader = FilePromptLoader(FIXTURE_PROMPTS)
    loader.load_all()

    system_prompt = PromptComposer(loader).compose_system_prompt()

    assert '"intent": "generate_image"' in system_prompt
    assert "ASCII art" in system_prompt
