from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from robotic_assist_child_server.app import create_app
from robotic_assist_child_server.config.settings import Settings

FIXTURE_PROMPTS = Path(__file__).parent / "fixtures" / "prompts"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        prompts_repository_path=str(FIXTURE_PROMPTS),
        deployment_environment="test",
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
