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

    # Authentication (access token only; refresh token deferred).
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 60

    # Relational database. Falls back to a local SQLite file when unset, so the
    # MVP runs without PostgreSQL; Docker Compose provides POSTGRES_DSN.
    database_url: str | None = None
    postgres_dsn: str | None = None

    # MongoDB for per-user memory. When unset, an in-memory repository is used
    # so the MVP/tests run without MongoDB; Docker Compose provides MONGODB_URI.
    mongodb_uri: str | None = None
    mongodb_database: str = "rac"

    # Conversation provider. Fake remains the default so local development runs
    # without external API keys.
    conversation_provider: str = "fake"
    conversation_temperature: float = 0.4
    conversation_max_tokens: int = 700
    conversation_timeout_seconds: float = 30.0

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "openai/gpt-5.4-nano"
    openrouter_chat_model_fallback: str = "openai/gpt-5.4-mini"
    openrouter_http_referer: str = "http://localhost:8080"
    openrouter_app_title: str = "Robotic Assist Child"
    openrouter_fallback_to_fake: bool = True
    openrouter_max_retries: int = 2

    # Image generation. Disabled by default; fake provider keeps local
    # development and tests independent from external APIs.
    image_provider: str = "fake"
    image_generation_enabled: bool = False
    openrouter_image_model: str = "google/gemini-3.1-flash-image-preview"
    image_storage_path: str = "/app/data/images"
    public_image_base_url: str = "http://localhost:8080/v1/images"
    image_output_format: str = "png"
    image_timeout_seconds: float = 60.0
    image_max_retries: int = 1
    image_fallback_to_fake: bool = True
    image_default_aspect_ratio: str = "1:1"
    image_default_size: str = "800x800"

    # Prepared connection settings (unused by the MVP slice).
    redis_url: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @property
    def resolved_database_url(self) -> str:
        return (
            self.database_url
            or self.postgres_dsn
            or "sqlite+aiosqlite:///./rac_dev.db"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
