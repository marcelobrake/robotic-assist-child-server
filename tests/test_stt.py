from __future__ import annotations

from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from robotic_assist_child_server.app import create_app
from robotic_assist_child_server.application.ports.speech import (
    SpeechProviderConfigurationError,
    SpeechTranscriptionRequest,
)
from robotic_assist_child_server.domain.entities import TextInteraction
from robotic_assist_child_server.domain.enums import ClientType
from robotic_assist_child_server.application.services.speech_intent_classifier import (
    RuleBasedSpeechIntentClassifier,
)
from robotic_assist_child_server.shared.datetime import utc_now
from robotic_assist_child_server.infrastructure.elevenlabs import (
    ElevenLabsSpeechToTextProvider,
    FakeSpeechToTextProvider,
)
from robotic_assist_child_server.infrastructure.openai import (
    OpenAISpeechToTextProvider,
)


def _audio_files(text: str = "Oi Cubinho!", content_type: str = "audio/wav"):
    return {"audio_file": ("speech.wav", text.encode("utf-8"), content_type)}


def _transcription_request(audio: bytes) -> SpeechTranscriptionRequest:
    return SpeechTranscriptionRequest(
        audio=audio,
        content_type="audio/wav",
        filename="speech.wav",
        session_id="session_1",
        user_id="usr_1",
    )


# --- Provider unit tests -------------------------------------------------


async def test_fake_stt_decodes_uploaded_bytes() -> None:
    provider = FakeSpeechToTextProvider()

    result = await provider.transcribe(_transcription_request(b"Oi Cubinho!"))

    assert result.text == "Oi Cubinho!"
    assert result.provider == "fake"


async def test_fake_stt_rejects_binary_audio_payload() -> None:
    provider = FakeSpeechToTextProvider()

    with pytest.raises(RuntimeError, match="Fake STT cannot transcribe binary audio"):
        await provider.transcribe(_transcription_request(b"\x00\x00\x00 ftypM4A audio"))


async def test_elevenlabs_stt_builds_expected_request() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["xi_api_key"] = request.headers.get("xi-api-key")
        captured["authorization"] = request.headers.get("Authorization")
        captured["content_type"] = request.headers.get("content-type")
        captured["body"] = await request.aread()
        return httpx.Response(200, json={"text": "uma história sobre dinossauros"})

    provider = ElevenLabsSpeechToTextProvider(
        api_key="test-key",
        base_url="https://elevenlabs.test",
        model="scribe_v2",
        timeout_seconds=30,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await provider.transcribe(_transcription_request(b"audio-bytes"))

    assert result.text == "uma história sobre dinossauros"
    assert result.provider == "elevenlabs"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://elevenlabs.test/v1/speech-to-text"
    assert captured["xi_api_key"] == "test-key"
    # Never leaks a bearer token; ElevenLabs authenticates via xi-api-key only.
    assert captured["authorization"] is None
    assert "multipart/form-data" in str(captured["content_type"])
    assert b'filename="speech.wav"' in captured["body"]


async def test_openai_stt_builds_expected_request() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = await request.aread()
        return httpx.Response(200, json={"text": "olá mundo"})

    provider = OpenAISpeechToTextProvider(
        api_key="sk-test",
        base_url="https://openai.test/v1",
        model="gpt-4o-mini-transcribe",
        timeout_seconds=30,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await provider.transcribe(_transcription_request(b"audio-bytes"))

    assert result.text == "olá mundo"
    assert result.provider == "openai"
    assert captured["url"] == "https://openai.test/v1/audio/transcriptions"
    assert captured["authorization"] == "Bearer sk-test"
    assert b'filename="speech.wav"' in captured["body"]


async def test_openai_stt_raises_configuration_error_on_unauthorized() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = OpenAISpeechToTextProvider(
        api_key="sk-invalid",
        base_url="https://openai.test/v1",
        model="gpt-4o-mini-transcribe",
        timeout_seconds=30,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(SpeechProviderConfigurationError):
        await provider.transcribe(_transcription_request(b"audio-bytes"))


async def test_elevenlabs_stt_raises_on_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "bad request"})

    provider = ElevenLabsSpeechToTextProvider(
        api_key="test-key",
        base_url="https://elevenlabs.test",
        model="scribe_v2",
        timeout_seconds=30,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await provider.transcribe(_transcription_request(b"audio-bytes"))


# --- Intent classifier unit tests ---------------------------------------


def test_intent_classifier_decisions() -> None:
    classifier = RuleBasedSpeechIntentClassifier()

    assert not classifier.classify("").should_respond
    assert classifier.classify("").reason == "no_speech"
    assert not classifier.classify("teste").should_respond
    assert not classifier.classify("é").should_respond
    assert not classifier.classify("oi").should_respond  # bare greeting
    assert classifier.classify("Cubinho, me conta uma história").should_respond
    assert classifier.classify("você pode desenhar um gato?").should_respond
    assert classifier.classify("oi amigo, tudo bem").should_respond
    assert not classifier.classify("a mãe foi na cozinha agora").should_respond


# --- Endpoint tests ------------------------------------------------------


def test_audio_interaction_rejects_invalid_content_type(client: TestClient) -> None:
    response = client.post(
        "/v1/interactions/audio",
        files={"audio_file": ("note.txt", b"hello", "text/plain")},
        data={"client_type": "test"},
    )

    assert response.status_code == 415, response.text


def test_audio_interaction_rejects_oversized_upload(settings) -> None:
    settings.max_audio_upload_mb = 1
    app = create_app(settings)
    payload = b"x" * (1 * 1024 * 1024 + 1)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/audio",
            files={"audio_file": ("big.wav", payload, "audio/wav")},
            data={"client_type": "test"},
        )

    assert response.status_code == 413, response.text


def test_audio_interaction_returns_transcribed_text(client: TestClient) -> None:
    response = client.post(
        "/v1/interactions/audio",
        files=_audio_files("Oi Cubinho!"),
        data={"client_type": "test"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["input_text"] == "Oi Cubinho!"
    assert body["assistant_text"]
    assert body["status"] == "accepted"
    assert body["audio"] is None


def test_audio_interaction_with_generate_audio_reuses_tts(settings) -> None:
    settings.tts_enabled = True
    settings.tts_provider = "fake"
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/audio",
            files=_audio_files("Oi Cubinho!"),
            data={"client_type": "test", "generate_audio": "true"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["audio"] is not None
    assert body["audio"]["content_type"] == "audio/wav"

    audio_path = urlparse(body["audio"]["audio_url"]).path
    audio_response = test_client.get(audio_path)
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/wav")
    assert audio_response.content


def test_audio_interaction_listener_mode_off_responds(client: TestClient) -> None:
    response = client.post(
        "/v1/interactions/audio",
        files=_audio_files("alguma coisa qualquer aqui"),
        data={"client_type": "test", "listener_mode": "false"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"


def test_audio_interaction_listener_mode_ignores_empty(client: TestClient) -> None:
    response = client.post(
        "/v1/interactions/audio",
        files=_audio_files("   "),
        data={"client_type": "test", "listener_mode": "true"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ignored"
    assert body["intent"] == "ignored"
    assert body["expression"] == "idle"
    assert body["assistant_text"] is None
    assert body["audio"] is None
    assert body["ignored_reason"] == "no_speech"


def test_audio_interaction_listener_mode_responds_when_addressed(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/interactions/audio",
        files=_audio_files("Cubinho, me conta uma história"),
        data={"client_type": "test", "listener_mode": "true"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["input_text"] == "Cubinho, me conta uma história"
    assert body["assistant_text"]


def test_audio_interaction_stt_failure_returns_friendly_error(settings) -> None:
    settings.stt_enabled = True
    settings.stt_provider = "elevenlabs"
    settings.elevenlabs_api_key = None
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/audio",
            files=_audio_files("audio bytes"),
            data={"client_type": "test", "generate_audio": "true"},
        )

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == (
        "Não consegui entender o áudio agora. Tente novamente."
    )


def test_audio_interaction_openai_auth_failure_returns_actionable_error(settings) -> None:
    settings.stt_enabled = True
    settings.stt_provider = "openai"
    settings.openai_api_key = None
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/audio",
            files=_audio_files("audio bytes"),
            data={"client_type": "test", "generate_audio": "true"},
        )

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == (
        "STT não autorizado. Verifique a chave OpenAI no backend."
    )


def test_audio_interaction_fake_stt_binary_payload_returns_friendly_error(
    settings,
) -> None:
    settings.stt_enabled = False
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/audio",
            files={
                "audio_file": (
                    "speech.m4a",
                    b"\x00\x00\x00 ftypM4A audio bytes",
                    "audio/m4a",
                )
            },
            data={"client_type": "test", "generate_audio": "true"},
        )

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == (
        "Não consegui entender o áudio agora. Tente novamente."
    )


async def test_ignored_interaction_not_persisted_by_default(settings) -> None:
    settings.store_ignored_interactions = False
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/audio",
            files=_audio_files("   "),
            data={"client_type": "test", "listener_mode": "true"},
        )
        body = response.json()
        container = test_client.app.state.container

    assert body["status"] == "ignored"
    stored = await container.interaction_repository.get(body["interaction_id"])
    assert stored is None


async def test_listener_mode_accepts_short_contextual_follow_up(settings) -> None:
    app = create_app(settings)

    with TestClient(app) as test_client:
        container = test_client.app.state.container
        await container.interaction_repository.save(
            TextInteraction(
                interaction_id="int_previous_followup",
                session_id="session_followup",
                user_id="usr_1",
                client_type=ClientType.TEST,
                input_text="Explique frações.",
                response_text="Quer que eu dê outro exemplo?",
                created_at=utc_now(),
                status="accepted",
            )
        )
        response = test_client.post(
            "/v1/interactions/audio",
            files=_audio_files("sim"),
            data={
                "client_type": "test",
                "listener_mode": "true",
                "session_id": "session_followup",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["input_text"] == "sim"


async def test_ignored_interaction_persisted_when_enabled(settings) -> None:
    settings.store_ignored_interactions = True
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/audio",
            files=_audio_files("   "),
            data={"client_type": "test", "listener_mode": "true"},
        )
        body = response.json()
        container = test_client.app.state.container

    stored = await container.interaction_repository.get(body["interaction_id"])
    assert stored is not None
    assert stored.status == "ignored"
