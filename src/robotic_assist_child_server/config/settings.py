"""Application settings.

Loading order (per AGENT.md): environment variables, then `.env` fallback.
AWS Secrets Manager / Parameter Store providers are prepared as future
adapters (see config/providers.py) but not implemented in the MVP slice.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "robotic-assist-child-server"
    service_version: str = "0.1.0"
    deployment_environment: str = "local"
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000

    # Path to the mounted/sibling prompts repository.
    prompts_repository_path: str = "../robotic-assist-child-prompts"

    # Local development auth bypass (never default-on in prod-like envs).
    dev_auth_disabled: bool = False

    # Prepared connection settings (unused by the MVP slice).
    postgres_dsn: str | None = None
    mongodb_uri: str | None = None
    redis_url: str | None = None
    otel_exporter_otlp_endpoint: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
