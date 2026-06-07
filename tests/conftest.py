from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from robotic_assist_child_server.app import create_app
from robotic_assist_child_server.config.settings import Settings

FIXTURE_PROMPTS = Path(__file__).parent / "fixtures" / "prompts"


def _base_settings(**overrides: object) -> Settings:
    values = {
        "prompts_repository_path": str(FIXTURE_PROMPTS),
        "deployment_environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "postgres_dsn": None,
        "mongodb_uri": None,
        "jwt_secret": "test-secret",
        "dev_auth_disabled": False,
        "conversation_provider": "fake",
        "openrouter_api_key": None,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings() -> Settings:
    return _base_settings()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def dev_settings() -> Settings:
    return _base_settings(dev_auth_disabled=True)


@pytest.fixture
def dev_client(dev_settings: Settings) -> TestClient:
    app = create_app(dev_settings)
    with TestClient(app) as test_client:
        yield test_client
