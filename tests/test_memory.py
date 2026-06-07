from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from robotic_assist_child_server.application.services.memory_updater import (
    RuleBasedMemoryUpdater,
)
from robotic_assist_child_server.domain.enums import MemoryType
from robotic_assist_child_server.infrastructure.repositories import (
    InMemoryMemoryRepository,
)


# --- RuleBasedMemoryUpdater (unit) ---------------------------------------- #


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Eu gosto de dinossauros", "Gosta de dinossauros."),
        ("gosto de sorvete!", "Gosta de sorvete."),
        ("Meu favorito é o azul.", "Gosta de o azul."),
    ],
)
async def test_updater_extracts_interest(text: str, expected: str) -> None:
    repo = InMemoryMemoryRepository()
    updater = RuleBasedMemoryUpdater(repo)

    created = await updater.evaluate(
        user_id="usr_1", session_id="session_1", input_text=text
    )

    assert len(created) == 1
    assert created[0].memory_type == MemoryType.INTEREST
    assert created[0].content == expected
    stored = await repo.list_for_user("usr_1")
    assert [m.content for m in stored] == [expected]


async def test_updater_ignores_non_matching_text() -> None:
    repo = InMemoryMemoryRepository()
    updater = RuleBasedMemoryUpdater(repo)

    created = await updater.evaluate(
        user_id="usr_1", session_id="session_1", input_text="Vamos brincar?"
    )

    assert created == []
    assert await repo.list_for_user("usr_1") == []


async def test_updater_is_idempotent_for_same_interest() -> None:
    repo = InMemoryMemoryRepository()
    updater = RuleBasedMemoryUpdater(repo)

    await updater.evaluate(user_id="usr_1", session_id="s", input_text="gosto de pizza")
    await updater.evaluate(user_id="usr_1", session_id="s", input_text="gosto de pizza")

    assert len(await repo.list_for_user("usr_1")) == 1


async def test_updater_skips_anonymous_user() -> None:
    repo = InMemoryMemoryRepository()
    updater = RuleBasedMemoryUpdater(repo)

    created = await updater.evaluate(
        user_id="", session_id="s", input_text="gosto de carros"
    )
    assert created == []


# --- HTTP endpoints (dev-auth bypass uses dev_user) ----------------------- #


def test_create_and_list_memory(dev_client: TestClient) -> None:
    create = dev_client.post(
        "/v1/memories",
        json={"content": "Gosta de dinossauros.", "memory_type": "interest"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["memory_id"].startswith("mem_")
    assert body["user_id"] == "dev_user"
    assert body["created_at"].endswith("Z")

    listing = dev_client.get("/v1/memories")
    assert listing.status_code == 200
    data = listing.json()
    assert data["count"] == 1
    assert data["memories"][0]["content"] == "Gosta de dinossauros."


def test_memories_require_authentication(client: TestClient) -> None:
    assert client.get("/v1/memories").status_code == 401


def test_interaction_creates_interest_memory(dev_client: TestClient) -> None:
    interaction = dev_client.post(
        "/v1/interactions/text", json={"text": "Eu gosto de dinossauros"}
    )
    assert interaction.status_code == 200
    assert interaction.json()["user_id"] == "dev_user"

    listing = dev_client.get("/v1/memories")
    contents = [m["content"] for m in listing.json()["memories"]]
    assert "Gosta de dinossauros." in contents


def test_authenticated_interaction_creates_memory(client: TestClient) -> None:
    register = client.post(
        "/v1/auth/register",
        json={"username": "parent_bia", "password": "s3cret!"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/v1/interactions/text",
        json={"text": "gosto de sorvete"},
        headers=headers,
    )

    listing = client.get("/v1/memories", headers=headers)
    contents = [m["content"] for m in listing.json()["memories"]]
    assert "Gosta de sorvete." in contents
