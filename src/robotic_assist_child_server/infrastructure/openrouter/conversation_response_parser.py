"""Parse model output into the child-safe conversation response contract."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace

from ...application.ports.conversation_provider import ConversationResponse

_tracer = trace.get_tracer(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.I)
_ALLOWED_EXPRESSIONS = {
    "idle",
    "happy",
    "thinking",
    "listening",
    "speaking",
    "surprised",
    "confused",
    "error",
}
_ALLOWED_INTENTS = {"chat", "generate_image", "activity", "story", "fallback"}

SAFE_PARSE_FALLBACK = (
    "Vamos falar de outra coisa bem legal? Estou aqui para brincar com você."
)


@dataclass(frozen=True, slots=True)
class ParsedConversationResponse:
    response: ConversationResponse
    is_contract_valid: bool
    fallback_reason: str | None = None


class ConversationResponseParser:
    def parse(self, raw_content: str) -> ParsedConversationResponse:
        with _tracer.start_as_current_span("conversation.response.parse") as span:
            candidate = self._extract_json_candidate(raw_content)
            if candidate is None:
                span.set_attribute("conversation.response.parse.outcome", "plain_text")
                return self._fallback("plain_text")

            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                span.set_attribute("conversation.response.parse.outcome", "invalid_json")
                return self._fallback("invalid_json")

            if not isinstance(payload, dict):
                span.set_attribute("conversation.response.parse.outcome", "invalid_shape")
                return self._fallback("invalid_shape")

            parsed = self._from_payload(payload)
            span.set_attribute(
                "conversation.response.parse.outcome",
                "valid" if parsed.is_contract_valid else "contract_fallback",
            )
            return parsed

    @staticmethod
    def _extract_json_candidate(raw_content: str) -> str | None:
        content = (raw_content or "").strip()
        if not content:
            return None
        if content.startswith("{") and content.endswith("}"):
            return content

        block = _JSON_BLOCK_RE.search(content)
        if block:
            return block.group(1)

        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return content[start : end + 1]
        return None

    def _from_payload(self, payload: dict[str, Any]) -> ParsedConversationResponse:
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._fallback("missing_text")

        expression = payload.get("expression")
        if expression not in _ALLOWED_EXPRESSIONS:
            expression = "happy"

        intent = payload.get("intent")
        if intent not in _ALLOWED_INTENTS:
            intent = "chat"

        image_prompt = payload.get("image_prompt")
        if not isinstance(image_prompt, str):
            image_prompt = None

        return ParsedConversationResponse(
            response=ConversationResponse(
                text=text.strip(),
                expression=str(expression),
                intent=str(intent),
                image_prompt=image_prompt,
            ),
            is_contract_valid=True,
        )

    @staticmethod
    def _fallback(reason: str) -> ParsedConversationResponse:
        return ParsedConversationResponse(
            response=ConversationResponse(
                text=SAFE_PARSE_FALLBACK,
                expression="confused",
                intent="fallback",
                image_prompt=None,
            ),
            is_contract_valid=False,
            fallback_reason=reason,
        )
