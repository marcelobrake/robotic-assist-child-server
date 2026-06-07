"""Minimal child-safety guard.

Intentionally simple and conservative for the MVP slice. It does not attempt
real moderation; it enforces basic rules from the prompts repository:
- never request personal data from the child;
- never encourage secrets from parents;
- redirect unsafe requests gently with a short, calm message.

Implements the SafetyGuardPort protocol.
"""
from __future__ import annotations

from ...shared.errors import UnsafeContentError

MAX_INPUT_LENGTH = 2000

# Lowercase substrings that trigger a gentle redirect instead of a model call.
_UNSAFE_INPUT_MARKERS = (
    "senha",
    "password",
    "endereço",
    "endereco",
    "telefone",
    "cartão",
    "cartao",
    "segredo dos pais",
    "não conte aos meus pais",
    "nao conte aos meus pais",
    "arma",
    "machucar",
    "matar",
)

# Markers that, if present in a generated response, force a safe fallback.
_UNSAFE_RESPONSE_MARKERS = (
    "me diga seu endereço",
    "me diga sua senha",
    "não conte aos seus pais",
    "nao conte aos seus pais",
)

REDIRECT_MESSAGE = (
    "Isso é coisa de gente grande. Que tal a gente brincar ou "
    "conversar sobre algo divertido? Você pode perguntar para o papai também."
)

SAFE_FALLBACK_MESSAGE = (
    "Vamos falar de outra coisa bem legal? Estou aqui para brincar com você."
)


class SafetyGuard:
    def validate_input_text(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            raise UnsafeContentError("O texto da criança está vazio.")
        if len(cleaned) > MAX_INPUT_LENGTH:
            cleaned = cleaned[:MAX_INPUT_LENGTH]
        return cleaned

    def is_safe_request(self, text: str) -> bool:
        lowered = text.lower()
        return not any(marker in lowered for marker in _UNSAFE_INPUT_MARKERS)

    def validate_assistant_response(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return SAFE_FALLBACK_MESSAGE
        lowered = cleaned.lower()
        if any(marker in lowered for marker in _UNSAFE_RESPONSE_MARKERS):
            return SAFE_FALLBACK_MESSAGE
        return cleaned

    @property
    def redirect_message(self) -> str:
        return REDIRECT_MESSAGE
