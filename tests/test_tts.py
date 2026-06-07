from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from robotic_assist_child_server.app import create_app
from robotic_assist_child_server.application.ports.speech import (
    SpeechSynthesisRequest,
)
from robotic_assist_child_server.infrastructure.audio import LocalAudioStore
from robotic_assist_child_server.infrastructure.elevenlabs import (
    ElevenLabsTextToSpeechProvider,
    FakeTextToSpeechProvider,
)

_MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00fake-mp3-payload"


def _store(tmp_path: Path) -> LocalAudioStore:
    return LocalAudioStore(
        storage_path=str(tmp_path / "audio"),
        public_base_url="http://testserver/v1/audio",
    )


def _request() -> SpeechSynthesisRequest:
    return SpeechSynthesisRequest(
        text="Oi! Eu sou o Cubinho.",
        session_id="session_1",
        user_id="usr_1",
    )


def _elevenlabs_provider(
    tmp_path: Path, transport: httpx.MockTransport
) -> ElevenLabsTextToSpeechProvider:
    return ElevenLabsTextToSpeechProvider(
        api_key="test-key",
        base_url="https://elevenlabs.test",
        voice_id="voice_123",
        model="eleven_flash_v2_5",
        output_format="mp3_44100_128",
        timeout_seconds=30,
        max_retries=0,
        audio_store=_store(tmp_path),
        http_client=httpx.AsyncClient(transport=transport),
    )


async def test_fake_tts_provider_synthesizes_and_stores(tmp_path: Path) -> None:
    store = _store(tmp_path)
    provider = FakeTextToSpeechProvider(audio_store=store)

    audio = await provider.synthesize(_request())

    assert audio.audio_id.startswith("aud_")
    assert audio.audio_url == f"http://testserver/v1/audio/{audio.audio_id}"
    assert audio.content_type == "audio/wav"
    assert audio.provider == "fake"
    stored = store.resolve(audio.audio_id)
    assert stored is not None
    assert stored.path.exists()
    assert stored.path.read_bytes().startswith(b"RIFF")


async def test_elevenlabs_provider_builds_expected_request(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["xi_api_key"] = request.headers.get("xi-api-key")
        captured["authorization"] = request.headers.get("Authorization")
        captured["content"] = request.content.decode("utf-8")
        return httpx.Response(
            200, content=_MP3_BYTES, headers={"content-type": "audio/mpeg"}
        )

    provider = _elevenlabs_provider(tmp_path, httpx.MockTransport(handler))
    audio = await provider.synthesize(_request())

    assert audio.provider == "elevenlabs"
    assert audio.content_type == "audio/mpeg"
    assert captured["method"] == "POST"
    assert (
        captured["url"]
        == "https://elevenlabs.test/v1/text-to-speech/voice_123?output_format=mp3_44100_128"
    )
    assert captured["xi_api_key"] == "test-key"
    # Never sends an Authorization header that could leak via proxies/logs.
    assert captured["authorization"] is None
    assert "eleven_flash_v2_5" in str(captured["content"])


async def test_elevenlabs_provider_raises_on_error(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "bad request"})

    provider = _elevenlabs_provider(tmp_path, httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        await provider.synthesize(_request())


def test_text_interaction_without_generate_audio_returns_null(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/interactions/text",
        json={"input_text": "Oi Cubinho!", "client_type": "test"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["audio"] is None


def test_text_interaction_with_generate_audio_fake_provider(settings) -> None:
    settings.tts_enabled = True
    settings.tts_provider = "fake"
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/text",
            json={
                "input_text": "Oi Cubinho!",
                "client_type": "test",
                "generate_audio": True,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["audio"] is not None
        audio_id = body["audio"]["audio_id"]
        assert body["audio"]["content_type"] == "audio/wav"
        audio_response = test_client.get(f"/v1/audio/{audio_id}")

    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"] == "audio/wav"


def test_text_interaction_keeps_audio_null_when_tts_disabled(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/interactions/text",
        json={
            "input_text": "Oi Cubinho!",
            "client_type": "test",
            "generate_audio": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["audio"] is None


def test_get_audio_returns_404_when_missing(client: TestClient) -> None:
    response = client.get("/v1/audio/aud_missing")

    assert response.status_code == 404


def test_text_interaction_survives_tts_failure(settings) -> None:
    """An ElevenLabs error must never break the textual reply."""
    settings.tts_enabled = True
    settings.tts_provider = "elevenlabs"
    settings.elevenlabs_api_key = None  # forces the provider to raise
    settings.elevenlabs_voice_id = "voice_123"
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/text",
            json={
                "input_text": "Oi Cubinho!",
                "client_type": "test",
                "generate_audio": True,
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_text"]
    assert body["audio"] is None
