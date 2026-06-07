from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SafetyGuardPort(Protocol):
    """Port for validating child-facing input and assistant responses."""

    def validate_input_text(self, text: str) -> str:
        """Return safe text or raise UnsafeContentError / return a redirect."""
        ...

    def validate_assistant_response(self, text: str) -> str:
        """Return a safe response, sanitizing or redirecting if needed."""
        ...
