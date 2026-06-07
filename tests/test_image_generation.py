from __future__ import annotations

import base64
from io import BytesIO
import json
import struct
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from robotic_assist_child_server.app import create_app
from robotic_assist_child_server.application.ports import ImageGenerationRequest
from robotic_assist_child_server.infrastructure.images import LocalImageStore
from robotic_assist_child_server.infrastructure.openrouter import (
    FakeImageGenerationProvider,
    OpenRouterImageGenerationProvider,
)

def _make_png_bytes(size: tuple[int, int] = (16, 16)) -> bytes:
    image = Image.new("RGB", size, color=(40, 130, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


_PNG_BYTES = _make_png_bytes()


def _image_size(path: str | Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _request() -> ImageGenerationRequest:
    return ImageGenerationRequest(
        prompt="Um foguete azul indo para a lua.",
        session_id="session_1",
        user_id="usr_1",
    )


def _store(tmp_path: Path) -> LocalImageStore:
    return LocalImageStore(
        storage_path=str(tmp_path / "images"),
        public_base_url="http://testserver/v1/images",
        default_output_format="png",
    )


def _openrouter_provider(
    tmp_path: Path, transport: httpx.MockTransport
) -> OpenRouterImageGenerationProvider:
    image_store = _store(tmp_path)
    fake_provider = FakeImageGenerationProvider(image_store=image_store)
    return OpenRouterImageGenerationProvider(
        api_key="test-key",
        base_url="https://openrouter.test/api/v1",
        image_model="google/gemini-3.1-flash-image-preview",
        http_referer="http://localhost:8080",
        app_title="Robotic Assist Child",
        timeout_seconds=60,
        max_retries=0,
        fallback_to_fake=True,
        output_format="png",
        image_store=image_store,
        fake_provider=fake_provider,
        http_client=httpx.AsyncClient(transport=transport),
    )


async def test_fake_image_generation_provider_works(tmp_path: Path) -> None:
    store = _store(tmp_path)
    provider = FakeImageGenerationProvider(image_store=store)

    image = await provider.generate(_request())

    assert image.image_id.startswith("img_")
    assert image.image_url == f"http://testserver/v1/images/{image.image_id}"
    assert image.content_type == "image/png"
    assert image.provider == "fake"
    stored = store.resolve(image.image_id)
    assert stored is not None
    assert stored.path.exists()
    width, height = struct.unpack(">II", stored.path.read_bytes()[16:24])
    assert (width, height) == (800, 800)


async def test_openrouter_image_provider_builds_expected_request(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    encoded = base64.b64encode(_PNG_BYTES).decode("ascii")

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["http_referer"] = request.headers.get("HTTP-Referer")
        captured["x_title"] = request.headers.get("X-Title")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "images": [
                                {
                                    "image_url": {
                                        "url": f"data:image/png;base64,{encoded}"
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    provider = _openrouter_provider(tmp_path, httpx.MockTransport(handler))
    image = await provider.generate(_request())

    assert image.provider == "openrouter"
    assert image.model == "google/gemini-3.1-flash-image-preview"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["http_referer"] == "http://localhost:8080"
    assert captured["x_title"] == "Robotic Assist Child"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "google/gemini-3.1-flash-image-preview"
    assert payload["modalities"] == ["image", "text"]
    assert payload["image_config"] == {"aspect_ratio": "1:1", "image_size": "1K"}
    assert payload["stream"] is False
    assert _request().prompt in payload["messages"][0]["content"][0]["text"]
    assert "800x800" in payload["messages"][0]["content"][0]["text"]


async def test_openrouter_image_provider_parses_base64_response(
    tmp_path: Path,
) -> None:
    encoded = base64.b64encode(_PNG_BYTES).decode("ascii")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    provider = _openrouter_provider(tmp_path, httpx.MockTransport(handler))
    image = await provider.generate(_request())

    assert image.content_type == "image/png"
    assert _image_size(image.storage_path or "") == (800, 800)


async def test_openrouter_image_provider_ignores_reasoning_data(
    tmp_path: Path,
) -> None:
    encoded = base64.b64encode(_PNG_BYTES).decode("ascii")
    encrypted_reasoning = base64.b64encode(b"not-an-image").decode("ascii")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "reasoning_details": [
                                {
                                    "type": "reasoning.encrypted",
                                    "data": encrypted_reasoning,
                                    "format": "google-gemini-v1",
                                }
                            ],
                            "images": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{encoded}"
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    provider = _openrouter_provider(tmp_path, httpx.MockTransport(handler))
    image = await provider.generate(_request())

    assert image.content_type == "image/png"
    assert _image_size(image.storage_path or "") == (800, 800)


async def test_openrouter_image_provider_parses_url_response(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://images.test/result.png":
            return httpx.Response(
                200, content=_PNG_BYTES, headers={"content-type": "image/png"}
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "https://images.test/result.png"},
                                }
                            ]
                        }
                    }
                ]
            },
        )

    provider = _openrouter_provider(tmp_path, httpx.MockTransport(handler))
    image = await provider.generate(_request())

    assert image.content_type == "image/png"
    assert _image_size(image.storage_path or "") == (800, 800)


def test_get_image_returns_404_when_missing(client: TestClient) -> None:
    response = client.get("/v1/images/img_missing")

    assert response.status_code == 404


def test_text_interaction_returns_image_when_enabled_with_fake_provider(
    settings,
) -> None:
    settings.image_generation_enabled = True
    settings.image_provider = "fake"
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v1/interactions/text",
            json={
                "input_text": "Cubinho, desenha um foguete azul indo para a lua.",
                "client_type": "test",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["intent"] == "generate_image"
        assert body["image"] is not None
        image_id = body["image"]["image_id"]
        image_response = test_client.get(f"/v1/images/{image_id}")

    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"


def test_text_interaction_keeps_image_null_when_generation_disabled(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/interactions/text",
        json={
            "input_text": "Cubinho, desenha um foguete azul indo para a lua.",
            "client_type": "test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "generate_image"
    assert body["image"] is None


def test_text_interaction_retry_reexecutes_previous_failed_image_request(
    client: TestClient,
) -> None:
    first = client.post(
        "/v1/interactions/text",
        json={
            "session_id": "session_retry_image",
            "input_text": "Cubinho, desenha um foguete azul indo para a lua.",
            "client_type": "test",
        },
    )
    assert first.status_code == 200
    assert first.json()["intent"] == "generate_image"
    assert first.json()["image"] is None

    retry = client.post(
        "/v1/interactions/text",
        json={
            "session_id": "session_retry_image",
            "input_text": "tente novamente",
            "client_type": "test",
        },
    )

    assert retry.status_code == 200
    body = retry.json()
    assert body["input_text"] == "tente novamente"
    assert body["intent"] == "generate_image"
    assert "foguete azul" in (body["image_prompt"] or "")
    assert body["image"] is None
