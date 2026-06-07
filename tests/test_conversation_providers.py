from __future__ import annotations

import json

import httpx

from robotic_assist_child_server.application.ports import (
    ConversationMessage,
    ConversationRequest,
)
from robotic_assist_child_server.infrastructure.openrouter import (
    ConversationResponseParser,
    FakeConversationProvider,
    OpenRouterConversationProvider,
)


def _request() -> ConversationRequest:
    return ConversationRequest(
        system_prompt="system prompt",
        user_text="Oi Cubinho!",
        session_id="session_1",
        user_id="usr_1",
        messages=(
            ConversationMessage(role="system", content="system prompt"),
            ConversationMessage(role="user", content="Oi Cubinho!"),
        ),
    )


def _elaborated_request() -> ConversationRequest:
    base = _request()
    return ConversationRequest(
        system_prompt=base.system_prompt,
        user_text="Me conta uma história curta.",
        session_id=base.session_id,
        user_id=base.user_id,
        messages=base.messages,
        metadata={"response_detail": "elaborated"},
    )


def _provider(
    transport: httpx.MockTransport,
    *,
    max_retries: int = 0,
) -> OpenRouterConversationProvider:
    return OpenRouterConversationProvider(
        api_key="test-key",
        base_url="https://openrouter.test/api/v1",
        chat_model="openai/gpt-5.4-nano",
        chat_model_fallback="openai/gpt-5.4-mini",
        http_referer="http://localhost:8080",
        app_title="Robotic Assist Child",
        temperature=0.4,
        max_tokens=700,
        timeout_seconds=30,
        max_retries=max_retries,
        fallback_to_fake=True,
        fake_provider=FakeConversationProvider(),
        http_client=httpx.AsyncClient(transport=transport),
    )


async def test_fake_conversation_provider_still_works() -> None:
    response = await FakeConversationProvider().generate(_request())

    assert response.text
    assert response.expression == "happy"
    assert response.intent == "chat"


async def test_openrouter_provider_builds_expected_request() -> None:
    captured: dict[str, object] = {}

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
                            "content": json.dumps(
                                {
                                    "text": "Oi! Vamos brincar.",
                                    "expression": "happy",
                                    "intent": "chat",
                                    "image_prompt": None,
                                }
                            )
                        }
                    }
                ]
            },
        )

    provider = _provider(httpx.MockTransport(handler))
    response = await provider.generate(_request())

    assert response.text == "Oi! Vamos brincar."
    assert captured["method"] == "POST"
    assert captured["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["http_referer"] == "http://localhost:8080"
    assert captured["x_title"] == "Robotic Assist Child"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "openai/gpt-5.4-nano"
    assert payload["temperature"] == 0.4
    assert payload["max_tokens"] == 700
    assert payload["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "Oi Cubinho!"},
    ]


async def test_openrouter_provider_can_select_elaborated_model() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "text": "Era uma vez um dinossauro gentil.",
                                    "expression": "happy",
                                    "intent": "story",
                                    "image_prompt": None,
                                }
                            )
                        }
                    }
                ]
            },
        )

    provider = _provider(httpx.MockTransport(handler))
    response = await provider.generate(_elaborated_request())

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "openai/gpt-5.4-mini"
    assert response.intent == "story"


def test_parser_accepts_valid_json() -> None:
    parsed = ConversationResponseParser().parse(
        '{"text":"Olá!","expression":"happy","intent":"chat","image_prompt":null}'
    )

    assert parsed.is_contract_valid is True
    assert parsed.response.text == "Olá!"
    assert parsed.response.expression == "happy"


def test_parser_extracts_json_from_markdown_block() -> None:
    parsed = ConversationResponseParser().parse(
        """```json
{"text":"Era uma vez um dino.","expression":"happy","intent":"story","image_prompt":null}
```"""
    )

    assert parsed.is_contract_valid is True
    assert parsed.response.intent == "story"
    assert parsed.response.text == "Era uma vez um dino."


def test_parser_converts_plain_text_to_safe_fallback() -> None:
    parsed = ConversationResponseParser().parse("texto solto")

    assert parsed.is_contract_valid is False
    assert parsed.fallback_reason == "plain_text"
    assert parsed.response.intent == "fallback"
    assert "brincar" in parsed.response.text


async def test_openrouter_provider_uses_fake_fallback_on_error() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": "temporary"})

    provider = _provider(httpx.MockTransport(handler), max_retries=1)
    response = await provider.generate(_request())

    assert calls == 2
    assert response.text
    assert response.intent == "chat"
