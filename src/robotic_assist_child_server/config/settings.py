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

    # Text-to-speech (TTS). Disabled by default; fake provider keeps local
    # development and tests independent from external APIs. No input audio is
    # stored and the API key/headers are never logged.
    tts_provider: str = "fake"
    tts_enabled: bool = False
    tts_output_format: str = "mp3_44100_128"
    tts_storage_path: str = "/app/data/audio"
    public_audio_base_url: str = "http://localhost:8080/v1/audio"
    elevenlabs_api_key: str | None = None
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_voice_id: str | None = None
    elevenlabs_tts_model: str = "eleven_flash_v2_5"
    elevenlabs_tts_timeout_seconds: float = 30.0
    elevenlabs_tts_max_retries: int = 2
    # Speaking rate sent in voice_settings.speed. ElevenLabs accepts 0.7-1.2;
    # 1.0 is the natural pace and higher values speak faster.
    elevenlabs_tts_speed: float = 1.1

    # Speech-to-text (STT). Disabled by default; fake provider decodes uploaded
    # bytes as text so local development and tests need no external API. Input
    # audio is never stored and API keys are never logged.
    stt_provider: str = "elevenlabs"
    stt_enabled: bool = False
    elevenlabs_stt_model: str = "scribe_v2"
    elevenlabs_stt_realtime_model: str = "scribe_v2_realtime"
    elevenlabs_stt_timeout_seconds: float = 30.0
    openai_api_key: str | None = None
    openai_stt_base_url: str = "https://api.openai.com/v1"
    openai_stt_model: str = "gpt-4o-mini-transcribe"
    openai_stt_timeout_seconds: float = 30.0

    # Audio upload / interaction policy.
    max_audio_upload_mb: int = 10
    audio_input_retention: str = "none"
    store_ignored_interactions: bool = False

    # Listener (continuous-listening) mode.
    listener_mode_require_addressing: bool = True
    listener_mode_allowed_triggers: str = (
        "Cubinho,oi,olá,ei,conta,desenha,explica,me ajuda,brinca"
    )

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

    @property
    def max_audio_upload_bytes(self) -> int:
        return max(1, self.max_audio_upload_mb) * 1024 * 1024

    @property
    def listener_mode_triggers(self) -> list[str]:
        return [
            trigger.strip()
            for trigger in self.listener_mode_allowed_triggers.split(",")
            if trigger.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
